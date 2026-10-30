"""P3 壳（Symbol Details / News / Calendars / Brokers）：先把结构做起来。

这些 TradingView 插件的**内容需要数据源**（新闻 / 基本面 / 日历 / 券商），
pylightcharts 本身不提供，所以这里是**壳**：UI 结构与数据契约就绪，宿主喂数据即可。

本示例把 6 个壳摆成 3×2 网格：

- 经济日历 `EconomicCalendar`（重要性用颜色区分）
- 基本面 `FundamentalData`
- 券商评级 `BrokerRating`
- 券商评价 `BrokerReviews`
- 公司资料 `CompanyProfile`（报价头 + 文本块）
- 新闻头条 `NewsFeed`（= Top Stories）

运行::

    python examples/13_panels/08_details.py
    python examples/13_panels/08_details.py --snapshot details.png
"""
from __future__ import annotations

import argparse
import importlib
import os
import sys

BINDING = os.environ.get('PYLIGHTCHARTS_QT') or 'PySide6'
os.environ['PYLIGHTCHARTS_QT'] = BINDING

from pylightcharts.qt import prepare_qt                      # noqa: E402

prepare_qt(BINDING)
QtCore = importlib.import_module(f'{BINDING}.QtCore')
QtWidgets = importlib.import_module(f'{BINDING}.QtWidgets')

from pylightcharts import QtPanel                            # noqa: E402
from pylightcharts.panels import (BrokerRating, BrokerReviews,  # noqa: E402
                                   CompanyProfile, EconomicCalendar,
                                   FundamentalData, NewsFeed)

CALENDAR = [
    {'time': '20:30', 'country': 'US', 'event': 'CPI 月率', 'importance': '高',
     'actual': '0.3%', 'forecast': '0.3%', 'previous': '0.4%'},
    {'time': '22:00', 'country': 'US', 'event': '成屋销售', 'importance': '中',
     'actual': '—', 'forecast': '4.10M', 'previous': '4.02M'},
    {'time': '09:30', 'country': 'CN', 'event': '官方制造业 PMI', 'importance': '高',
     'actual': '50.2', 'forecast': '50.0', 'previous': '49.8'},
    {'time': '14:00', 'country': 'DE', 'event': 'IFO 商业景气', 'importance': '低',
     'actual': '—', 'forecast': '87.5', 'previous': '87.0'},
]

FUNDAMENTALS = [
    {'name': '市盈率(TTM)', 'value': 28.4, 'yoy': 0.12, 'period': '2024Q4'},
    {'name': '市净率', 'value': 6.1, 'yoy': -0.03, 'period': '2024Q4'},
    {'name': 'ROE', 'value': 0.36, 'yoy': 0.05, 'period': '2024Q4'},
    {'name': '营收(亿)', 'value': 3910, 'yoy': 0.02, 'period': '2024Q4'},
    {'name': '净利润(亿)', 'value': 970, 'yoy': 0.08, 'period': '2024Q4'},
]

RATINGS = [
    {'broker': '高盛', 'rating': '买入', 'target': 210, 'upside': 0.10, 'date': '2025-01-12'},
    {'broker': '摩根士丹利', 'rating': '增持', 'target': 205, 'upside': 0.07,
     'date': '2025-01-10'},
    {'broker': '美银', 'rating': '中性', 'target': 185, 'upside': -0.03, 'date': '2025-01-08'},
]

REVIEWS = [
    {'broker': '高盛', 'review': '服务稳定，研报质量高', 'score': 4.5, 'date': '2025-01-05'},
    {'broker': '美银', 'review': '费率略高', 'score': 3.8, 'date': '2024-12-28'},
]

NEWS = [
    {'title': '央行维持利率不变，符合预期', 'source': 'Reuters', 'time': '10:24',
     'summary': '政策委员会一致决定维持利率，并强调将根据数据调整。'},
    {'title': '某品种库存降至年内低位', 'source': '文华财经', 'time': '09:50'},
    {'title': '海外需求回暖，出口数据超预期', 'source': 'Bloomberg', 'time': '08:31'},
    {'title': '机构上调明年盈利预测', 'source': '财联社', 'time': '07:55'},
]


def build(panel: QtPanel) -> None:
    panel.win.run_script(
        "var g=document.createElement('div');"
        "g.style.cssText='position:absolute;left:0;top:0;right:0;bottom:0;"
        "display:grid;grid-template-columns:1fr 1fr 1fr;grid-template-rows:1fr 1fr;"
        "gap:1px;background:#2a2e39';"
        "for(var i=0;i<6;i++){var c=document.createElement('div');c.id='__cell'+i;"
        "c.style.cssText='position:relative;min-width:0;min-height:0;"
        "background:#131722;overflow:hidden';g.appendChild(c);}"
        "document.getElementById('container').appendChild(g);")
    cell = "document.getElementById('__cell{0}')"

    EconomicCalendar(panel.win, CALENDAR, container=cell.format(0))
    FundamentalData(panel.win, FUNDAMENTALS, container=cell.format(1))
    BrokerRating(panel.win, RATINGS, container=cell.format(2))
    BrokerReviews(panel.win, REVIEWS, container=cell.format(3))
    CompanyProfile(
        panel.win,
        {'name': '苹果公司', 'symbol': 'AAPL', 'exchange': 'NASDAQ',
         'last': 190.2, 'chg': 1.5, 'chg_pct': 0.79},
        html='<p>苹果公司设计、制造并销售智能手机、个人电脑、平板电脑与可穿戴设备，'
             '并提供相关服务。</p><p class="pylc-text-muted">本页内容由宿主提供，'
             'pylightcharts 只负责渲染。</p>',
        container=cell.format(4))
    NewsFeed(panel.win, NEWS, container=cell.format(5))


def main() -> None:
    parser = argparse.ArgumentParser(description='P3 壳 示例')
    parser.add_argument('--snapshot', metavar='PNG', default=None)
    args = parser.parse_args()

    app = QtWidgets.QApplication(sys.argv)
    panel = QtPanel()
    build(panel)
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


if __name__ == '__main__':
    main()
