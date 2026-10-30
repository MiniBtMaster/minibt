"""按 `minibt_docs/mkdocs.yml` 的 nav 重新生成文档首页 `minibt_docs/docs/index.md`。

用途：首页长期手写会和导航脱节（新增章节忘了登记 / 编号对不上）。
这里以 **nav 为唯一数据源** 生成「章节导航」表与「完整目录」，其余
（简介 / 快速开始 / 资源）保持固定文案。

用法（仓库根目录）::

    python scripts/gen_minibt_docs_index.py
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = ROOT / 'minibt_docs' / 'docs'
NAV_FILE = ROOT / 'minibt_docs' / 'mkdocs.yml'

CN = ['一', '二', '三', '四', '五', '六', '七', '八', '九', '十',
      '十一', '十二', '十三', '十四', '十五', '十六', '十七', '十八']

#: 章节一句话介绍（新增章节时在这里补一行即可）
DESC = {
    '基本使用': '安装、5 分钟上手、核心类（Bt / Strategy / IndFrame / KLine / BtIndicator）、'
                'btplot、订单、止损、图表引擎九种模式、Gui.Desk',
    '交易策略': '18 个可直接抄的经典 / 创新策略：布林突破、TRIX、CMO、Hull、Keltner、'
                '配对交易、均值回归、随机森林…',
    'TradingView指标': '98 个 TradingView（Pine）指标 / 策略的 minibt 移植：SuperTrend、'
                       'UT Bot、QQE、Lorentzian、SMC…',
    '强化学习': 'RL 在量化里的应用、参数调优、算法选择、DDPG / DoubleDQN 实战与验证',
    '使用技巧': '25 条效率技巧与踩坑速查（另加总索引）：解包、`lines` 写法、`rolling_apply`、'
                '样式速查、性能陷阱、实盘 vs 回测、异常速查',
    'MiniQT使用教程': 'PyQt6 可视化客户端：报价 / 看盘 / 回测 / 优化 / 编辑器 / 模拟账户 / 设置',
    '图表样式': '`PlotInfo` 23 个字段 + 9 个样式类 + `Config`，逐字段配图讲解',
    '数据层': '`LocalDatas → KLine → IndFrame / IndSeries / Line`、数据源、resample、'
              '长度对齐、多合约、DataFrame 互操作',
    '指标库': '12 个指标库（PandasTa / TA-Lib / TuLip / FinTa / TqTa / Pine…）+ 自定义指标全流程',
    '订单与交易': '订单类型、目标仓位、冷却、反手、9 种止损、`stop_callback`、费用、'
                  '交易时段、日志、账户查询',
    '实时与实盘': '三种运行模式、tqsdk 接入、实时图表 / 面板、断线重连、futu、实盘调试',
    'IDE与工具链': 'VS Code 扩展、`btplot`、九种图表模式、Jupyter / notebook、打包与 FAQ',
    '行情终端（desk）': '**minibt desk** 桌面终端：报价 / 看盘 / 本地图表 / 回测 / 编辑器 / '
                        '交易 / 设置 + 使用手册 13.0~13.27',
    'API参考': '按模块的 API 说明 + 各指标库方法参考 + API 覆盖率报告',
}

#: 章节索引页（没有 index.md 的章节自动用第 1 篇）
INDEX = {
    '使用技巧': 'minibt_tips/index.md',
    '图表样式': 'minibt_styles/index.md',
    '数据层': 'minibt_data/index.md',
    '指标库': 'minibt_indicators/index.md',
    '订单与交易': 'minibt_orders/index.md',
    '实时与实盘': 'minibt_realtime/index.md',
    'IDE与工具链': 'minibt_ide/index.md',
    '行情终端（desk）': 'minibt_desk/index.md',
    'MiniQT使用教程': 'minibt_miniqt/6.1_index.md',
    'API参考': 'api/index.md',
}


def parse_nav() -> list:
    """解析 nav 里的「两级列表」（章节 → 条目），忽略注释行。"""
    lines = NAV_FILE.read_text(encoding='utf-8').splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == 'nav:')
    groups = []
    current = None
    for line in lines[start + 1:]:
        if line and not line.startswith(' '):
            break
        match = re.match(r'^(\s*)- (.*)$', line)
        if not match:
            continue
        indent = len(match.group(1))
        text = match.group(2).strip()
        if indent == 2 and text.endswith(':'):
            current = {'title': text[:-1], 'items': []}
            groups.append(current)
        elif indent >= 4 and current is not None and ': ' in text:
            label, _, path = text.partition(': ')
            current['items'].append((label.strip(), path.strip()))
    return groups


def build(groups: list) -> str:
    out = []
    out.append('# MiniBT 量化交易知识库\n')
    out.append('**一站式量化交易策略开发库**的完整文档：数据 → 指标 → 策略 → '
               '回测 / 参数优化 → 回放 → 实时 / 实盘 → 可视化'
               '（pylightcharts / bokeh / **minibt desk**）。\n')
    out.append('[5 分钟上手](minibt_basic/1.3minibt_double_moving_average_strategy.md)'
               '{ .md-button .md-button--primary } '
               '[安装](minibt_basic/1.2minibt_install.md){ .md-button } '
               '[图表九种模式](minibt_basic/1.29minibt_chart_modes.md){ .md-button } '
               '[minibt desk 终端](minibt_desk/index.md){ .md-button }\n')
    out.append(
        '!!! abstract "从这里开始"\n'
        '    * **第一次用** → [1.2 安装](minibt_basic/1.2minibt_install.md) → '
        '[1.3 双均线 5 分钟实战](minibt_basic/1.3minibt_double_moving_average_strategy.md)\n'
        '    * **想画图** → [1.17 btplot](minibt_basic/1.17minibt_interactive_financial_charting_with_btplot.md) → '
        '[1.29 图表引擎与九种模式](minibt_basic/1.29minibt_chart_modes.md) → '
        '[7.1 PlotInfo 心智模型](minibt_styles/7.1_plotinfo_overview.md)\n'
        '    * **想接实时 / 实盘** → [11.1 三种运行模式](minibt_realtime/11.1_modes.md) → '
        '[11.2 tqsdk 接入](minibt_realtime/11.2_tq_auth.md) → '
        '[11.8 实盘 vs 回测](minibt_realtime/11.8_live_vs_backtest.md)\n'
        '    * **想用桌面终端** → [13.1 行情终端 desk](minibt_desk/13.1_desk.md) → '
        '[13.0 使用手册](minibt_desk/manual/13.0_plan.md) → '
        '[1.33 Gui.Desk](minibt_basic/1.33minibt_desk_gui.md)（含 Jupyter 内嵌）\n'
        '    * **遇到报错** → [常见问题](faq.md) → '
        '[5.23 异常速查](minibt_tips/5.23_exceptions.md) → '
        '[5.25 图不显示排查树](minibt_tips/5.25_plot_not_showing.md)\n')

    out.append('## 快速开始\n')
    out.append('```bash\npip install minibt\n# 开发态：git clone 后\npip install -e .\n```\n')
    out.append(
        '```python\n'
        'from minibt import Bt, LocalDatas, Strategy\n\n\n'
        'class MyStrategy(Strategy):\n'
        '    def __init__(self):\n'
        '        self.data = self.get_kline(LocalDatas.test)\n'
        '        self.ma = self.data.close.sma(20)\n'
        '        self.ma.overlap = True\n\n'
        '    def next(self):\n'
        '        if self.data.close.new > self.ma.new and not self.data.position.pos:\n'
        '            self.data.buy()\n'
        '        elif self.data.close.new < self.ma.new and self.data.position.pos:\n'
        '            self.data.sell()\n\n\n'
        'Bt().run()          # 默认 pylightcharts 原生窗口；也可以 gui=Gui.Desk\n'
        '```\n')
    out.append('> 回测 / 回放 / 实时共 **9 种图表模式**（3 个引擎 × 3 个场景），'
               '另有 `Gui.Desk`（desk 界面）与 `Gui.Jupyter`（Notebook 内联）；'
               '详见 [1.29 图表引擎与九种运行模式](minibt_basic/1.29minibt_chart_modes.md)。\n')

    out.append('## 章节导航\n')
    out.append('| 章节 | 讲什么 | 入口 | 篇数 |\n| --- | --- | --- | --- |')
    for index, group in enumerate(groups):
        title = group['title']
        items = group['items']
        entry = INDEX.get(title)
        if entry is None:
            entry = items[0][1] if items else ''
            entry_label = '第 1 篇'
        else:
            entry_label = '本章索引'
        out.append(f'| **{CN[index]}、{title}** | {DESC.get(title, "")} | '
                   f'[{entry_label}]({entry}) | {len(items)} |')
    out.append('')
    out.append('> 另有：[常见问题](faq.md) · [关于我们](about.md) · '
               '[联系方式](contact.md) · [MiniBT 更新日志](changelog.md) · '
               '[MiniQT 更新日志](changelog_miniqt.md)\n')

    out.append('## 完整目录\n')
    out.append('> 与左侧导航（`mkdocs.yml`）一一对应；点标题展开 / 收起。\n')
    for index, group in enumerate(groups):
        title = group['title']
        items = group['items']
        block = [f'??? note "{CN[index]}、{title}（{len(items)} 篇）"', '']
        block.extend(f'    - [{label}]({path})' for label, path in items)
        out.append('\n'.join(block))
        out.append('')

    out.append('## 资源与反馈\n')
    out.append('- <i class="fa-brands fa-zhihu"></i> '
               '[知乎专栏](https://zhuanlan.zhihu.com/column/c_1942555756558783128)\n'
               '- <i class="fa-brands fa-globe"></i> [minibt 官网](https://www.minibt.cn)\n'
               '- <i class="fa-brands fa-github"></i> '
               '[GitHub 仓库](https://github.com/MiniBtMaster/minibt)\n'
               '- <i class="fa-brands fa-python"></i> [PyPI](https://pypi.org/project/minibt/)\n'
               '- 文档有问题 / 想补充：'
               '[提 Issue](https://github.com/MiniBtMaster/minibt/issues) · '
               '[联系方式](contact.md)\n')
    out.append('## 版本\n')
    out.append('- 当前文档对应 **minibt v1.3.x**；逐版本改动见 '
               '[MiniBT 更新日志](changelog.md)。\n'
               '- MiniQT 桌面客户端见 [六、MiniQT 使用教程](minibt_miniqt/6.1_index.md) 与 '
               '[MiniQT 更新日志](changelog_miniqt.md)。\n')
    return '\n'.join(out)


def main() -> int:
    groups = parse_nav()
    text = build(groups)
    target = DOCS / 'index.md'
    target.write_text(text, encoding='utf-8')
    total = sum(len(group['items']) for group in groups)
    print(f'wrote {target}（{len(groups)} 章 / {total} 篇）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
