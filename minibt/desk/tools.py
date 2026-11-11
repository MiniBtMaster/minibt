# coding: utf-8
"""PI 助手的「操控 desk」工具桥（v1.3.7-24，MCP 方案 M1）。

使用文档：`minibt_docs/docs/minibt_desk/manual/13.29_pi_mcp_usage.md`；
设计稿：`minibt_docs/docs/minibt_desk/13.29_pi_mcp_desk_control.md`：

* **一张方法表**：`SPECS`（OpenAI function-calling 格式）既是给模型的工具定义，
  以后也是 MCP `tools/list` 的输出（阶段二只换 transport ✓）；
* `call(name, args, desk)` 白名单分发，**只做适配** —— 内部调用 desk 已有的
  `_on_*` 处理器（不复制业务逻辑，避免两套实现走偏）；
* 每次调用写**审计日志** `~/.minibt/ai/audit.jsonl`（参数脱敏 ✓）；
* 需要用户提供密码 / 确认的危险动作返回 `need_user_input` / `need_confirm`，
  由模型**反问用户**，而不是自己瞎猜 ✓。

M1 = 只读 + 界面类（切合约 / 加指标 / 布局 / 打开页面 / 二级报价）。
交易类（下单 / 实盘）在 M2，必须先 `confirm=true`。
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List, Optional

#: 审计日志（每次 `desk_*` 调用一行 ✓）
AUDIT_FILE = os.path.join(os.path.expanduser('~'), '.minibt', 'ai',
                          'audit.jsonl')

#: 图表缩放（`desk_bars`）等前端回执的最长等待秒数（测试可调小 ✓）
BARS_TIMEOUT = 4.0

#: 参数里这些 key 要脱敏（密码 / key / token 永不落盘 ✓）
SECRET_KEYS = ('password', 'passwd', 'pwd', 'secret', 'token', 'apikey',
               'api_key', 'key')


def _tool(name: str, description: str,
          properties: Dict[str, Any],
          required: Optional[List[str]] = None) -> Dict[str, Any]:
    return {
        'type': 'function',
        'function': {
            'name': name,
            'description': description,
            'parameters': {'type': 'object', 'properties': properties,
                           **({'required': required} if required else {})},
        },
    }


def _num(description: str) -> Dict[str, Any]:
    return {'type': 'number', 'description': description}


def _int(description: str) -> Dict[str, Any]:
    return {'type': 'integer', 'description': description}


def _str(description: str) -> Dict[str, Any]:
    return {'type': 'string', 'description': description}


def _bool(description: str) -> Dict[str, Any]:
    return {'type': 'boolean', 'description': description}


#: M1 工具（全部**不涉及钱**：只切页面 / 加指标 / 看状态 ✓）
SPECS: List[Dict[str, Any]] = [
    _tool('desk_status',
          '看盘终端当前状态：打开的图表、合约、布局、本地图表列表、'
          '当前选中的合约（只读）',
          {}),
    _tool('desk_switch_symbol',
          '切换图表合约（看盘窗口的 K 线 / 指标 / 策略一起重来）',
          {'symbol': _str('合约代码，如 DCE.a2701 / SHFE.rb2601'),
           'cell': _int('多布局里第几格（0 = 第一格）'),
           'local': _bool('true = 本地图表，false = 实时图表')},
          ['symbol']),
    _tool('desk_clear_indicators',
          '清空某一页 / 某格的**所有指标**（不影响策略）',
          {'page': _str('本地图表页签 id（空 = 当前页）'),
           'symbol': _str('CSV 名（空 = 当前）'),
           'cell': _int('第几格（0 = 第一格）'),
           'local': _bool('true = 本地图表')}),
    _tool('desk_find_indicator',
          '按关键词找指标 → 精确 key（**先查再加**，别猜：MACD 有很多版本）',
          {'query': _str('关键词 / 名字，如 macd / boll / ma / pandas_ta.macd'),
           'limit': _int('返回几条（默认 10）')},
          ['query']),
    _tool('desk_add_indicator',
          '给图表加**一个**指标（内建 / TradingView / 我的脚本）；key 支持别名'
          '（pandas_ta.macd → pta_macd）；不确定先 desk_find_indicator',
          {'key': _str('指标 key 或常见写法：MACD / pta_macd / pandas_ta.macd'),
           'symbol': _str('哪个合约（空=当前合约）'),
           'params': {'type': 'object', 'description': '指标参数（可空）'},
           'cell': _int('多布局里第几格（0 = 第一格）'),
           'page': _str('本地图表页签 id（空 = 当前页）'),
           'symbol': _str('本地图表：数据集名（空 = 当前格，自动取）'),
           'local': _bool('true = 本地图表')},
          ['key']),
    _tool('desk_remove_indicator',
          '从图表上删掉一个指标',
          {'key': _str('指标 key'),
           'symbol': _str('哪个合约（空=当前合约）'),
           'cell': _int('第几格（0 = 第一格）'),
           'page': _str('本地图表页签 id（空 = 当前页）'),
           'local': _bool('true = 本地图表')},
          ['key']),
    _tool('desk_set_layout',
          '切布局；`local=true` 时按 `symbols` 给本地图表**逐格**装数据集',
          {'cols': _int('列数（1 / 2 / 3）'),
           'rows': _int('行数（1 / 2）'),
           'symbol': _str('实时图表：哪个合约页（空=当前）'),
           'symbols': {'type': 'array', 'items': {'type': 'string'},
                       'description': '本地图表：每格的 CSV 名，如 '
                                      '["test","l2609_60"]'},
           'page': _str('本地图表页签 id（空 = 当前页）'),
           'local': _bool('true = 本地图表（按 symbols 组布局）')}),
    _tool('desk_local',
          '本地图表：list 数据集（CSV 名字 + 条数）/ load 加载成图表 / '
          'pages 列出已打开的页与每格 CSV',
          {'action': _str('list / load / pages（默认 list）'),
           'name': _str('load：数据集名字（来自 action=list）'),
           'page': _str('load：页签 id（空 = 当前页）')},
          []),
    _tool('desk_book',
          '二级报价：read（默认，取五档）/ open 打开右侧面板 / close 关闭 / '
          'toggle 切换 / watch 订阅盘口（顺带打开面板）/ off 退订',
          {'action': _str('read / open / close / toggle / watch / off'
                          '（默认 read）'),
           'symbol': _str('合约代码（空=当前合约）'),
           'page': _str('页签 id（如 chart:DCE.a2701 / local:1；'
                        '空=当前页）'),
           'cell': _int('第几格（0 = 第一格）'),
           'open': _bool('watch 时是否同时打开面板（默认 true）')}),
    _tool('desk_open_page',
          '打开页面：本地图表 / 实时图表 / 策略回测 / 参数优化',
          {'kind': _str('local_chart / chart / backtest / optimize / '
                        'home / quote / settings / logs / palette'),
           'name': _str('本地数据集名字（local_chart 用）'),
           'symbol': _str('合约代码（chart 用）'),
           'file': _str('策略 .py 路径（backtest / optimize 用）')},
          ['kind']),
    _tool('desk_backtest_run',
          '跑策略回测（后台跑；结果看 desk_strategy_status）',
          {'file': _str('策略 .py 路径'),
           'params': {'type': 'object', 'description': '策略参数覆盖（可空）'},
           'symbol': _str('合约（空 = 用策略自己选的）')},
          ['file']),
    _tool('desk_optimize_run',
          '跑参数优化（后台跑；结果看 desk_strategy_status）',
          {'file': _str('策略 .py 路径'),
           'params': {'type': 'object', 'description': '基础参数（可空）'},
           'options': {'type': 'object', 'description': '优化选项（可空）'},
           'targets': {'type': 'array', 'items': {'type': 'string'},
                       'description': '优化目标指标（可空）'}},
          ['file']),
    _tool('desk_strategy_status',
          '看回测 / 优化的会话与正在跑的策略实盘（只读）', {}),
    _tool('desk_account',
          '账户只读（下单前先 summary 看一眼）：summary 登录 / 账户 / 资金概览 · '
          'positions 持仓 · orders 全部委托（含已撤 / 被拒）· unfilled 未成交'
          '（真实挂单）· trades 成交明细 · pending 挂单摘要 · audit 委托审计；'
          'local=true 看本地模拟账户',
          {'action': _str('summary（默认）/ positions / orders / unfilled / '
                          'trades / pending / audit'),
           'local': _bool('true = 本地模拟账户'),
           'key': _str('账户 key：kq / real / futu（空 = 当前页的账户）'),
           'symbol': _str('合约（空 = 当前图表）')}),
    _tool('desk_order',
          '**下真单**（只允许限价单；必须先问过用户并带 confirm=true）。'
          '会先检查交易是否已登录：没连上直接返回 need_login，不会假装提交 ✓',
          {'symbol': _str('合约代码'),
           'side': _str('buy / sell'),
           'volume': _int('手数'),
           'price': _num('限价（必须 > 0）'),
           'offset': _str('open / close（平今 / 平昨会按今仓 / 昨仓'
                          '自动拆，不用自己区分 ✓）'),
           'local': _bool('true = 本地模拟账户'),
           'account': _str('哪个账户（空 = 当前）'),
           'confirm': _bool('用户确认后才传 true')},
          ['symbol', 'side', 'volume', 'price', 'confirm']),
    _tool('desk_strategy_live',
          '**策略实盘 / 模拟盘**：start 会真实下单（要 confirm=true），stop 随时停',
          {'file': _str('策略 .py 路径'),
           'action': _str('start / stop'),
           'confirm': _bool('start 时必须用户确认')},
          ['file', 'action', 'confirm']),
    _tool('desk_set_cycle',
          '切图表周期（按格）。**周期单位是秒**：5 分钟 = 300；也认 "5m" / '
          '"5分钟" / "1h" / "1d" 这类写法；不支持的周期会被拒绝且**不会清图**',
          {'cycle': _str('周期：300（=5分钟）/ "5m" / "1h" / "1d" / 60 …'),
           'symbol': _str('哪个图表（空 = 当前）'),
           'cell': _int('第几格（0 = 第一格）')},
          ['cycle']),
    _tool('desk_open_chart',
          '打开一个实时图表（行情不可用会给出原因）',
          {'symbol': _str('合约代码（空 = 当前合约）')}),
    _tool('desk_close_chart',
          '关闭一个实时图表',
          {'symbol': _str('合约代码（空 = 当前合约）')}),
    _tool('desk_replay',
          '回放：进入（start）/ 退出（exit）；**本地图表要 local=true**',
          {'action': _str('start / exit'),
           'local': _bool('true = 本地图表（走页面里的回放按钮）'),
           'page': _str('本地图表页签 id（空 = 当前页）'),
           'name': _str('本地数据集名（空 = 当前格）'),
           'symbol': _str('合约代码（实时图表；空 = 当前）'),
           'cycle': _int('周期（可空）'),
           'count': _int('回放多少根（可空 = 用图表历史长度）')}),
    _tool('desk_indicator_picker',
          '打开指标选择器让**用户**自己挑（**不会添加任何指标**，别用它代替 add）',
          {'symbol': _str('哪个图表（空 = 当前）'),
           'local': _bool('true = 本地图表'),
           'page': _str('本地图表页签 id（空 = 当前页）'),
           'cell': _int('第几格（0 = 第一格）')}),
    _tool('desk_templates',
          '列出已保存的指标模板（只读）', {}),
    _tool('desk_apply_template',
          '把某个指标模板应用到图表',
          {'key': _str('模板 key（来自 desk_templates）'),
           'symbol': _str('哪个图表（空 = 当前）'),
           'local': _bool('true = 本地图表'),
           'page': _str('本地图表页签 id（空 = 当前页）'),
           'cell': _int('第几格（0 = 第一格）'),
           'params': {'type': 'object', 'description': '参数覆盖（可空）'}},
          ['key']),
    _tool('desk_save_template',
          '把当前图表的指标保存成模板',
          {'name': _str('模板名（空 = 自动命名）'),
           'symbol': _str('哪个图表（空 = 当前）'),
           'local': _bool('true = 本地图表'),
           'page': _str('本地图表页签 id（空 = 当前页）'),
           'cell': _int('第几格（0 = 第一格）')}),
    _tool('desk_layouts',
          '布局：list（默认）/ apply 应用 / save 保存当前 / delete 删除 / '
          'favorite 收藏 / export 导出文本',
          {'action': _str('list / apply / save / delete / favorite / export'),
           'key': _str('布局 key（apply / delete / favorite 用）'),
           'name': _str('布局名（save 用，空 = 自动）'),
           'on': _bool('favorite：true 收藏 / false 取消'),
           'path': _str('export：写到这个文件（空 = 只返回文本）'),
           'symbol': _str('实时图表：哪个合约页（空 = 当前）'),
           'page': _str('本地图表页签 id（空 = 当前页）'),
           'local': _bool('true = 本地图表布局')},
          []),
    _tool('desk_editor_add_indicator',
          '把某个**.py 文件里**的指标 / 策略加到图表（编辑器「加到图表」同一条）',
          {'path': _str('指标 / 策略 .py 的完整路径'),
           'symbol': _str('哪个图表（空 = 当前）'),
           'local': _bool('true = 本地图表'),
           'page': _str('本地图表页签 id（空 = 当前页）'),
           'cell': _int('第几格（0 = 第一格）'),
           'overlay': _bool('true = 只读叠加（不交易）')},
          ['path']),
    _tool('desk_editor_open',
          '在 desk 编辑器里打开一个文件（只读展示，不修改）',
          {'path': _str('文件完整路径')},
          ['path']),
    _tool('desk_editor_save',
          '把源码写进文件（会重新扫描个人指标/策略目录）',
          {'path': _str('文件完整路径'),
           'text': _str('要写入的完整源码'),
           'format': _bool('true = 写入前用 ruff/black 格式化')},
          ['path', 'text']),
    _tool('desk_editor_new',
          '按模板新建指标 / 策略文件（名字空 = 自动命名）',
          {'kind': _str('indicator / strategy'),
           'name': _str('文件名（不含目录，可空）'),
           'overwrite': _bool('同名就覆盖')}),
    _tool('desk_editor_delete',
          '删除一个文件（危险动作，删除前请跟用户确认）',
          {'path': _str('文件完整路径')},
          ['path']),
    _tool('desk_editor_check',
          '语法检查（不写盘）：给 path 或 text',
          {'path': _str('文件路径（与 text 二选一）'),
           'text': _str('直接检查这段源码')}),
    _tool('desk_explorer_set_root',
          '把资源管理器根目录切到指定目录',
          {'path': _str('目录完整路径')},
          ['path']),
    _tool('desk_explorer_system_dir',
          '切到系统目录：个人指标 / 个人策略 / 两者根目录',
          {'kind': _str('indicator / strategy / all')}),
    _tool('desk_explorer_op',
          '资源管理器右键操作（新建文件/文件夹、重命名、删除、复制、剪切、粘贴）',
          {'action': _str('new_file / new_folder / rename / delete / copy / '
                          'cut / paste'),
           'path': _str('目标文件或目录'),
           'name': _str('新名字（rename / new_* 用）')},
          ['action']),
    _tool('desk_strategy_manage',
          '看策略管理里的行 + 「新K线 next」「next 运行」两个开关（只读）', {}),
    _tool('desk_strategy_switch',
          '开 / 关策略的两个运行开关（next_on_new_bar / run_next）',
          {'next_on_new_bar': _bool('true = 只在新 K 线跑 next'),
           'run_next': _bool('true = 指标算完就跑 next')}),
    _tool('desk_strategy_remove',
          '删掉图上的策略（指标保留）',
          {'symbol': _str('哪个图表（空 = 当前）')}),
    _tool('desk_repl_eval',
          '在 desk 的 REPL 里跑一段 Python（同步返回输出，最长 30 秒）',
          {'code': _str('要执行的 Python 代码'),
           'timeout': _num('超时秒数（默认 30）')},
          ['code']),
    _tool('desk_terminal_run',
          '在 desk 底部终端里执行一条 shell 命令（输出在终端面板）',
          {'command': _str('要执行的命令'),
           'cwd': _str('工作目录（可空 = 当前根目录）')},
          ['command']),

    _tool('desk_tv',
          '「指标和策略」页：list 卡片列表 / detail 详情 / source 源码 / star 收藏 / '
          'live 用在线行情换数据 / script 落成 .py 并在编辑器打开 / reload 重载卡片',
          {'action': _str('list / detail / source / star / live / script / reload'),
           'key': _str('指标 key（detail / source / star / script 用）'),
           'query': _str('list：关键词（可空）'),
           'tab': _str('list：all / star 等（可空）'),
           'group': _str('list：分组（可空）'),
           'page': _int('list：第几页 / live：页签 id（可空）'),
           'size': _int('list：每页数量（默认 12）'),
           'on': _bool('star：true 收藏 / false 取消'),
           'symbol': _str('live：合约代码'),
           'cycle': _int('live：周期（默认 60）')},
          []),
    _tool('desk_replay_trade',
          '回放中的本地模拟交易（下单 / 平仓 / 反手 / 全平）',
          {'action': _str('order / close / reverse / all'),
           'symbol': _str('合约（空 = 当前）'),
           'side': _str('buy / sell（action=order 时必填）'),
           'volume': _int('手数'),
           'price': _num('价格（0 = 用当前回放价）'),
           'offset': _str('open / close'),
           'confirm': _bool('回放交易也要用户确认')},
          ['action', 'confirm']),
    _tool('desk_bars',
          '图表缩放（**等价右键菜单**）：all = 全部K线（一次看全），'
          'last = 最新K线 N 根（默认 300）。模型不用改设置里的长度 ✓',
          {'action': _str('all / last（默认 last）'),
           'count': _int('last：显示多少根（默认 300）'),
           'page': _str('图表页 id（空 = 当前图表 / 最近一格）'),
           'local': _bool('true = 本地图表，false = 实时图表'),
           'cell': _int('多布局第几格（0 = 第一格；空 = 最后点的那格）')},
          []),
    _tool('desk_market',
          '**行情数据 / 分析**（给模型真实数字，不用看截图）：'
          'analysis **一次给全套**（结构+体检+形态+摘要，推荐）/ summary 全套 / '
          'quote 报价 / klines OHLCV / indicator 指标数值 / '
          'levels 支撑阻力(前高低+斐波那契+成交量分布) / stats ATR·波动率·RSI·分位 / '
          'patterns K 线形态 / depth 五档买卖压力 / digest 紧凑文本总结',
          {'action': _str('analysis（推荐：一次全套）/ summary（默认）/ '
                          'quote / klines / indicator / levels / stats / '
                          'patterns / depth / digest'),
           'symbol': _str('合约（空 = 当前图表合约）'),
           'symbols': {'type': 'array', 'items': {'type': 'string'},
                       'description': 'quote / summary：多个合约（可空）'},
           'cycle': _str('周期：秒或 "5m" / "5分" / "1h"（空 = 当前周期）'),
           'limit': _int('取多少根 / 多少个点（默认 60，最大 500）'),
           'pattern_limit': _int('analysis / patterns：返回几个形态（默认 6）'),
           'key': _str('indicator：指标 key（可用 desk_find_indicator 查）'),
           'keys': {'type': 'array', 'items': {'type': 'string'},
                    'description': 'indicator：多个指标 key（可空）'},
           'params': {'type': 'object', 'description': '指标参数（可空）'},
           'local': _bool('true = 本地图表数据（CSV）'),
           'name': _str('local：CSV 数据集名（空 = 当前本地图表）')},
          []),
    _tool('desk_ta',
          '**技术分析**（信号制）：options 可选指标（带 signal 的内置 / 用户指标）/ '
          'snapshot 按模板算（震荡 / 趋势 / 其他三类，1 多 · 0 中立 · -1 空）/ '
          'set 保存模板 / reset 恢复默认 ✓',
          {'action': _str('options（默认）/ snapshot / templates / use / '
                          'save / delete / set / reset'),
           'name': _str('templates：模板名（use/save/delete 用）'),
           'symbol': _str('snapshot：合约（空 = 当前图表）'),
           'rows': {'type': 'array', 'items': {'type': 'object'},
                    'description': 'snapshot/set：模板条目 '
                                   '[{key, group, signal:{kind,level,direction,offset}}]'},
           'all': _bool('options：true = 列全部指标（默认只列带信号的）')},
          []),
    _tool('desk_news',
          '**资讯**（AkShare）：latest 最新快讯 / market 要闻 / symbol 个股新闻 / '
          'futures 期货新闻 / search 搜缓存；给模型真实标题与时间，不用猜 ✓',
          {'action': _str('latest（默认）/ market / symbol / futures / search / '
                          'status'),
           'symbol': _str('action=symbol：股票代码（600519 / 000001）'),
           'query': _str('action=search：关键词（只搜本地缓存）'),
           'limit': _int('返回多少条（默认 20，最大 200）'),
           'refresh': _bool('true = 立刻联网抓一次（默认先给缓存）')},
          []),
    _tool('desk_macro',
          '**宏观指标**（AkShare）：GDP / GDP 同比 / CPI 同比 / 制造业 PMI / '
          'PPI 同比 / M2 同比，返回最近 N 期（升序）+ 最新值 ✓',
          {'action': _str('list（默认，全部序列）/ series（指定 names）'),
           'names': {'type': 'array', 'items': {'type': 'string'},
                     'description': '序列 key：gdp / gdp_yoy / cpi / pmi / ppi / m2'},
           'limit': _int('每序列取几期（默认 12，最大 60）'),
           'refresh': _bool('true = 立刻联网抓一次（默认先给缓存）')},
          []),
    _tool('desk_fundamentals',
          '**标的资料**：期货 = contract 合约规则 / inventory 库存 / basis 基差；'
          '股票 = **富途快照（PE/PB/市值/股息）+ capital 资金流**（没连富途用 '
          'AkShare）+ financials 财务摘要 + notices 公告；给模型真实数字 ✓',
          {'action': _str('all（默认）/ contract / inventory / basis / profile / '
                          'financials / notices / capital'),
           'symbol': _str('合约或股票代码（如 SHFE.ag2612 / SSE.600519）'),
           'limit': _int('财务期数 / 公告条数（默认 8 / 40）')},
          ['symbol']),
    _tool('desk_calendar',
          '**财经日历**（百度股市通）：今天 / 未来 N 天的经济数据与事件'
          '（时间 / 地区 / 事件 / 公布 / 预期 / 前值 / 重要性）✓',
          {'action': _str('today（默认）/ week / day'),
           'days': _int('action=week：未来几天（默认 3，最大 7）'),
           'day': _str('action=day：`YYYY-MM-DD`'),
           'limit': _int('返回多少条（默认 40）'),
           'refresh': _bool('true = 立刻联网抓一次')},
          []),
    _tool('desk_scan',
          '**多合约批量筛**：一次算多个合约的指标并按条件挑（"哪些合约 MACD 金叉" / '
          '"RSI < 30"）；比逐合约调用省几十轮 ✓',
          {'symbols': {'type': 'array', 'items': {'type': 'string'},
                       'description': '合约列表（≤30；空 = 当前图表合约）'},
           'key': _str('指标 key（可用 desk_find_indicator 查，如 pta_macd）'),
           'keys': {'type': 'array', 'items': {'type': 'string'},
                    'description': '多个指标（第一个参与判断，可空）'},
           'params': {'type': 'object', 'description': '指标参数（可空）'},
           'op': _str('gt / lt / cross_up（上穿）/ cross_down（下穿）'),
           'value': _num('阈值 / 穿越价（cross_* 与 gt/lt 必填）'),
           'cycle': _str('周期：秒或 "5m"（空 = 图表周期）'),
           'limit': _int('每个合约取多少根算指标（默认 120）')},
          ['op']),
    _tool('desk_strategy_data',
          '**回测结果 / 策略信号**：summary 收益回撤胜率 / trades 逐笔 / '
          'equity 净值曲线 / signals 最新多空信号（数据来自策略实验室 ✓）',
          {'action': _str('summary（默认）/ trades / equity / signals'),
           'id': _str('策略实验室会话 id（空 = 最近一次）'),
           'limit': _int('返回多少条（默认 20）')},
          []),
    _tool('desk_screenshot',
          '给当前图表截图并保存成 PNG（返回文件路径 ✓）',
          {'name': _str('文件名（可空 = 自动）'),
           'page': _str('页签 id（空 = 当前图表）'),
           'timeout': _num('等待前端截图的最长秒数（默认 12）')}),
    _tool('desk_login_futures',
          '登录天勤（快期模拟 / 实盘）；没保存过就要 username + password',
          {'username': _str('天勤用户名（可空 = 用记住的）'),
           'password': _str('密码（可空 = 用记住的；不会落盘）'),
           'real': _bool('true = 实盘（需要资金账号 + 交易密码）'),
           'broker': _str('期货公司（实盘必填）'),
           'account': _str('资金账号（实盘必填）'),
           'trade_password': _str('交易密码（实盘必填；不会落盘）'),
           'remember': _bool('记住用户名（密码不落盘）')}),
    _tool('desk_login_stock',
          '连接富途 OpenD（模拟盘不用账号；需先启动并登录 FutuOpenD）',
          {'host': _str('网关地址（默认 127.0.0.1）'),
           'port': _int('网关端口（默认 11111）'),
           'trd_env': _str('SIMULATE / REAL'),
           'trade': _bool('是否启用交易（模拟默认开）')}),
    _tool('desk_account_kind',
          '切换账户：快期模拟 / 富途模拟 / TqAccount 实盘（按页独立）',
          {'key': _str('账户 key（空 = 列出可选账户）'),
           'page': _str('页签 id（空 = 首页）'),
           'cell': _int('第几格（可空）')}),
    _tool('desk_close_charts',
          '关闭实时图表页（全部 / 指定合约）',
          {'all': _bool('true = 全部关闭'),
           'symbols': {'type': 'array', 'items': {'type': 'string'},
                       'description': '要关闭的合约列表'}}),
    _tool('desk_theme',
          '切换应用主题（深色 / 浅色）',
          {'theme': _str('dark / light')},
          ['theme']),
    _tool('desk_position_action',
          '持仓行右键：市价平 / 反手 / 全平（**会真实交易**）',
          {'action': _str('close / reverse / all'),
           'symbol': _str('合约（空 = 当前）'),
           'confirm': _bool('用户确认后才传 true')},
          ['action', 'confirm']),
    _tool('desk_order_action',
          '委托行右键：撤销某一笔 / 撤销该合约全部挂单',
          {'action': _str('cancel / cancel_all'),
           'order_id': _str('要撤的委托号（action=cancel 必填）'),
           'symbol': _str('合约（空 = 当前）'),
           'confirm': _bool('用户确认后才传 true')},
          ['action', 'confirm']),
    _tool('desk_ticket_order',
          '买卖盘一点下单（买开 / 卖开 / 买平 / 卖平，按当前价；**会真实交易**）',
          {'symbol': _str('合约（空 = 当前）'),
           'side': _str('buy / sell'),
           'qty': _int('手数（默认 1）'),
           'offset': _str('open / close'),
           'price': _num('价格（空 = 当前价）'),
           'local': _bool('true = 本地模拟账户'),
           'confirm': _bool('用户确认后才传 true')},
          ['side', 'confirm']),
    _tool('desk_alerts',
          '列出当前所有价格预警（只读）', {}),
    _tool('desk_add_alert',
          '创建预警：**价格到价**或**指标信号**（kind=signal + key + op），'
          '可带触发动作（买入 / 卖出 / 平仓）',
          {'symbol': _str('合约代码'),
           'kind': _str('price（默认）/ signal'),
           'price': _num('触发价（kind=price 必填）'),
           'cross': _str('穿过 / 上穿 / 下穿（默认 穿过）'),
           'key': _str('signal：指标 key（desk_ta{action:"options"} 里有）'),
           'op': _str('signal：信号变成 buy / sell / neutral 时触发'),
           'signal': {'type': 'object',
                      'description': 'signal：信号定义（可空 = 用指标默认）'},
           'action': _str('none / buy / sell / close'),
           'qty': _int('触发后的手数（默认 1）'),
           'message': _str('提醒文字（可空）'),
           'expire': _int('多少秒后过期（0 = 不过期）'),
           'page': _str('页签 id（决定触发账户；可空）'),
           'cell': _int('第几格（可空）')},
          ['symbol']),
    _tool('desk_drop_alert',
          '删除预警：给 id，或给 symbol（删该合约全部），或 all=true',
          {'id': _int('预警 id（来自 desk_alerts）'),
           'symbol': _str('按合约删（删除该合约全部预警）'),
           'all': _bool('true = 清空全部预警')}),
    _tool('desk_cmd',
          '通用命令直通（白名单）：界面上的那些命令（切主题 / 开页面 / 拉资讯 / '
          '选策略 / 会话改名 / 截图 / 导出…）。下单 / 执行代码 / 改权限 / '
          '删数据被禁止，要用专用工具',
          {'cmd': _str('命令名，如 set_theme / info_news / favorites / '
                       'screenshot / pi_sessions'),
           'args': _str('命令参数对象（dict），如 {"theme":"light"}')},
          ['cmd']),
    _tool('desk_close_tabs',
          '关闭页面 / 编辑器页签 / PI 会话（全部或指定）',
          {'kind': _str('page（顶栏页面）/ editor（代码页签）/ pi（对话页签）'),
           'ids': {'type': 'array', 'items': {'type': 'string'},
                   'description': '要关的 id 列表（页面 id / 文件路径 / 会话 id）'},
           'all': _bool('true = 全部关闭')},
          ['kind']),
    _tool('desk_open_ui',
          '打开界面：日志 / 设置 / 命令面板 / 首页 / 行情报价 / 工作台 / 研究 / 登录',
          {'target': _str('logs / settings / palette / home / quote / '
                          'workspace / research / workbench / datahub / '
                          'ops / schedule / info / login'),
           'section': _str('设置页的分区（可空）'),
           'login': _str('登录类型：futures / stocks（target=login 用）')},
          ['target']),
    _tool('desk_datahub',
          '本地数据平台：list 数据文件 / query 跑 SQL / preview 预览（可重采样）/ '
          'quality 质量报告',
          {'action': _str('list / query / preview / quality（默认 list）'),
           'sql': _str('query：例如 select * from test limit 5'),
           'name': _str('preview / quality：数据名'),
           'rule': _str('preview：重采样规则（1min / 5min / 1h，可空）'),
           'limit': _int('query / preview：返回行数（默认 200 / 20）')},
          []),
    _tool('desk_ops',
          '运维：tokens 令牌 / tasks 定时任务列表 / task_add 新建任务 / '
          'task_update 改任务 / task_remove 删任务 / task_history 执行历史 / '
          'notify_config 配告警通道（企业微信 / 公众号 xtuis / 邮件 / 自定义 webhook）/ '
          'notify_test 发测试 / '
          'alert_rules 告警规则（哪些事推手机）/ alert_log 告警记录 / '
          'equity 净值与回撤 / '
          'task_run 立刻跑 / task_toggle 启停 / task_templates 模板库 / '
          'task_from_template 按模板建 / tasks_export 导出 / '
          'tasks_import 导入 / holidays 手工休市日',
          {'action': _str('tokens / token_issue / tasks / task_add / '
                          'task_update / task_remove / task_history / '
                          'task_run / task_toggle / holidays'),
           'name': _str('token_issue：令牌名；task_*：任务名'),
           'kind': _str('任务动作：tool（调 MCP 工具）/ sequence（多步串联）/ '
                        'ai（发提示词）/ builtin（内置小函数）'),
           'steps': _str('kind=sequence：步骤 JSON 数组，如 '
                         '[{"tool":"desk_news","args":{"refresh":true}},'
                         '{"tool":"desk_calendar","args":{"days":2}}]；'
                         'arg 里可用 $0.xxx 引用前面步骤的结果'),
           'when': _str('跑之前的前置条件 JSON，如 '
                        '{"tool":"desk_positions","path":"positions",'
                        '"op":"count","cmp":">","value":0}（不成立就跳过）'),
           'xtuis_token': _str('notify_config kind=xtuis：公众号 token'),
           'template': _str('task_from_template：模板名（先 task_templates）'),
           'task_name': _str('task_from_template：新任务名（默认用模板名）'),
           'data': _str('tasks_import：导出的 JSON 文本'),
           'overwrite': _bool('tasks_import：同名是否覆盖（默认跳过）'),
           'mode': _str('alert_rules：list / save / reset / settings'),
           'quiet': _str('alert_rules settings：{"enabled":true,'
                         '"start":"23:00","end":"08:00",'
                         '"allow_level":"error"}'),
           'digest': _str('alert_rules settings：{"enabled":true,'
                          '"at":"16:00"}'),
           'query': _str('alert_log：关键词（搜标题 / 正文 / 规则）'),
           'level': _str('alert_log：error / warning / info'),
           'rule': _str('alert_log：规则 id，如 trade_reject'),
           'days': _int('equity：最近多少天（默认 30）'),
           'key': _str('equity：账户 key（默认第一个）'),
           'rules': _str('alert_rules save：JSON 数组，如 '
                         '[{"id":"trade_fill","enabled":true}]'),
           'retries': _int('失败重试次数（0~5）'),
           'catch_up': _bool('停机后补跑（6 小时内错过的那一次）'),
           'notify': _str('结果推送：error（默认）/ always / never'),
           'tool': _str('kind=tool：工具名，如 desk_news / desk_market'),
           'args': _str('kind=tool：工具参数 JSON，如 {"action":"analysis"}'),
           'prompt': _str('kind=ai：提示词'),
           'allow_write': _bool('kind=ai：允许 AI 改界面（默认只读 ✓）'),
           'trigger': _str('触发：interval（每 N 秒）/ daily（每天 HH:MM）/ '
                           'after（前置任务成功后）/ manual'),
           'after': _str('trigger=after：前置任务名（逗号分隔，全部成功后跑）'),
           'depends_on': _str('定时任务的前置依赖（逗号分隔；没成功就跳过）'),
           'depends_window': _int('依赖多久内算数（秒，默认 86400）'),
           'every': _int('trigger=interval：间隔秒数'),
           'at': _str('trigger=daily：时刻 HH:MM'),
           'days': _str('trigger=daily：everyday / mon-fri / trading'),
           'skip_holidays': _bool('跳过手工标记的休市日'),
           'only_trading_hours': _bool('只在交易时段跑'),
           'enabled': _bool('建好就启用（默认停用）'),
           'day': _str('holidays：日期 YYYY-MM-DD'),
           'scopes': {'type': 'array', 'items': {'type': 'string'},
                      'description': 'token_issue：权限范围（默认 read）'},
           'on': _bool('task_toggle：true 启用 / false 停用')},
          []),
    _tool('desk_research',
          '研究平台：list 实验列表 / start 启动任务（grid / walkforward / batch）/ '
          'cancel 取消',
          {'action': _str('list / start / cancel（默认 list）'),
           'strategy': _str('start：策略 .py 路径'),
           'mode': _str('start：grid / walkforward / batch'),
           'symbols': {'type': 'array', 'items': {'type': 'string'},
                       'description': 'start：合约列表（可空）'},
           'params': {'type': 'object', 'description': 'start：参数空间（可空）'},
           'files': {'type': 'array', 'items': {'type': 'string'},
                     'description': 'start：批量模式的策略文件（可空）'},
           'windows': {'type': 'object', 'description': 'start：Walk-Forward 窗口'},
           'limit': _int('list：返回多少条（默认 20）')},
          []),
    _tool('desk_workbench_snapshot',
          '交易工作台快照：订单票 / 风控 / 持仓 / 挂单 / 审计（只读）', {}),
    _tool('desk_workbench_limits',
          '设置工作台风控（最大手数 / 单笔金额 / 日内笔数 / 启用）',
          {'limits': {'type': 'object',
                      'description': '如 {"enabled":true,"max_volume":10}'},
           'enabled': _bool('是否启用风控'),
           'max_volume': _int('单手最大手数'),
           'max_notional': _num('单笔最大金额'),
           'max_orders': _int('日内最多下单笔数')}),
    _tool('desk_sequence',
          '**一次调用执行多步**（≤6 步）：每步 {tool, args}，按顺序跑并汇总结果；'
          'args 可用 `$0.resolved` 引用前面步骤的结果（查→加 一步搞定）；'
          '危险工具（下单 / 实盘 / 撤单）不能放进这里',
          {'steps': {'type': 'array', 'items': {
              'type': 'object',
              'properties': {'tool': {'type': 'string'},
                             'args': {'type': 'object'}}},
              'description': '例如 [{"tool":"desk_find_indicator",'
                             '"args":{"query":"pandas_ta.macd"}},'
                             '{"tool":"desk_add_indicator",'
                             '"args":{"key":"$0.resolved","local":true}},'
                             '{"tool":"desk_replay","args":{"local":true}}]'}},
          ['steps']),
    _tool('desk_drawings',
          '画线：list 已保存 / clear 删除 / toolbox 左侧画线工具箱开 / 关'
          '（等价右键「画线」）',
          {'action': _str('list / clear / toolbox（默认 list）'),
           'symbol': _str('合约代码（空=当前合约）'),
           'cycle': _int('clear：周期（默认 60）'),
           'on': _bool('toolbox：true 打开 / false 收起来（空 = 切换）'),
           'page': _str('toolbox：图表页 id（空 = 当前图表）')}),
]

#: 工具名集合（`agent.TOOL_GROUPS` 用 ✓）
NAMES: List[str] = [spec['function']['name'] for spec in SPECS]

#: 需要 `confirm=true` 的工具（M2：下单 / 实盘）—— 缺 confirm 时**不执行**，
#: 返回 `need_confirm` 让模型去反问用户 ✓
DANGEROUS = {'desk_order', 'desk_strategy_live', 'desk_position_action',
             'desk_order_action', 'desk_ticket_order'}

#: 只读工具（关掉「允许操控」时**仍然可用** —— 看状态不是操控 ✓）
READONLY = {'desk_status', 'desk_book', 'desk_local_list', 'desk_drawings',
            'desk_positions', 'desk_orders', 'desk_strategy_status',
            'desk_market', 'desk_scan', 'desk_strategy_data', 'desk_news',
            'desk_calendar', 'desk_macro', 'desk_fundamentals', 'desk_ta'}

#: 会**花钱**的工具（设置里没打开「允许下单」时一律拒绝 ✓）
ORDER_TOOLS = {'desk_order', 'desk_strategy_live'}

#: 设置键（设置 → 「PI 操控 desk」✓）
SETTING_ALLOW = 'ai_desk_allow'      # 允许 PI 操控 desk（默认开）
SETTING_ORDER = 'ai_desk_order'      # 允许下单 / 实盘（默认**关**）


def flags() -> Dict[str, bool]:
    """读两个开关（读取失败按默认：允许操控、禁止下单 ✓）"""
    allow, order = True, False
    try:
        from . import user_prefs
        data = user_prefs.settings() or {}
        if data.get(SETTING_ALLOW) is False:
            allow = False
        order = bool(data.get(SETTING_ORDER))
    except Exception:                                        # noqa: BLE001
        pass
    return {'allow': allow, 'order': order}


#: 危险动作的中文说明（给模型转述给用户 ✓）
DANGER_TEXT = {
    'desk_order': '这会**真实下单**（真金白银）。请把合约 / 方向 / 手数 / 价格'
                  '复述给用户，等用户明确说「确认」后再带 confirm=true 调一次。',
    'desk_strategy_live': '启动策略实盘会**持续真实下单**。请先说明会跑哪个策略、'
                          '哪个合约，等用户明确确认后再带 confirm=true 调一次。',
    'desk_position_action': '平仓 / 反手 / 全平都会**真实成交**。请把合约、方向、'
                            '数量复述给用户，等用户确认后再带 confirm=true 调一次。',
    'desk_order_action': '撤单会取消用户正在挂的委托。请复述是哪笔 / 哪个合约，'
                         '等用户确认后再带 confirm=true 调一次。',
    'desk_ticket_order': '买卖盘下单按**当前价立即成交**（可能市价）。请复述合约、'
                         '方向、手数，等用户确认后再带 confirm=true 调一次。',
}


# ---------------------------------------------------------------- 审计
def audit(name: str, args: Dict[str, Any], result: str,
          session: str = '') -> None:
    """写一行审计（参数脱敏；失败也不影响主流程 ✓）"""
    payload = {
        'at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'tool': name,
        'args': _redact(args if isinstance(args, dict) else {}),
        'result': str(result or '')[:500],
        'session': str(session or ''),
    }
    try:
        os.makedirs(os.path.dirname(AUDIT_FILE), exist_ok=True)
        with open(AUDIT_FILE, 'a', encoding='utf-8') as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + '\n')
    except OSError:
        pass


def recent_audit(limit: int = 200) -> List[Dict[str, Any]]:
    """最近 N 条审计（新的在前 ✓）；文件不存在就给空列表"""
    rows: List[Dict[str, Any]] = []
    try:
        with open(AUDIT_FILE, 'r', encoding='utf-8', errors='replace') as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        return []
    return rows[-max(1, int(limit)):][::-1]


def clear_audit() -> int:
    """清空审计（返回删掉的行数 ✓）"""
    count = len(recent_audit(100000))
    try:
        os.makedirs(os.path.dirname(AUDIT_FILE), exist_ok=True)
        with open(AUDIT_FILE, 'w', encoding='utf-8'):
            pass
    except OSError:
        return 0
    return count


def _redact(value: Any, depth: int = 0) -> Any:
    if depth > 4:
        return '…'
    if isinstance(value, dict):
        rows = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(secret in lowered for secret in SECRET_KEYS):
                rows[key] = '***'
            else:
                rows[key] = _redact(item, depth + 1)
        return rows
    if isinstance(value, list):
        return [_redact(item, depth + 1) for item in value][:20]
    text = str(value)
    return text if len(text) < 200 else text[:200] + '…'


# ---------------------------------------------------------------- 小工具
def read_text_smart(path: str) -> str:
    """读文本（UTF-8 → GBK → latin-1；复用 agent 的判定 ✓）"""
    from . import agent as _agent
    with open(path, 'rb') as handle:
        return _agent.decode_bytes(handle.read())


def _clip(value: Any, size: int = 8000, depth: int = 0) -> Any:
    """把过长的字符串 / 列表裁短（**保持 JSON 合法** ✓）"""
    if depth > 4:
        return '…'
    if isinstance(value, str):
        return value if len(value) <= size else value[:size] + chr(10) + '……（已截断）'
    if isinstance(value, list):
        return [_clip(item, size, depth + 1) for item in value[:60]]
    if isinstance(value, dict):
        return {key: _clip(item, size, depth + 1)
                for key, item in value.items()}
    return value


#: ★ v1.3.7-86：界面上「工具参数」的**默认值**（有默认就填，没有就 `""` ✓）
UI_DEFAULTS: Dict[tuple, Any] = {
    ('desk_news', 'action'): 'latest',
    ('desk_news', 'limit'): 20,
    ('desk_news', 'refresh'): False,
    ('desk_calendar', 'days'): 3,
    ('desk_calendar', 'refresh'): False,
    ('desk_macro', 'limit'): 12,
    ('desk_market', 'action'): 'analysis',
    ('desk_bars', 'action'): 'last',
    ('desk_bars', 'count'): 500,
    ('desk_ta', 'action'): 'snapshot',
    ('desk_drawings', 'action'): 'list',
    ('desk_account', 'action'): 'positions',
    ('desk_book', 'action'): 'get',
    ('desk_tv', 'action'): 'list',
    ('desk_datahub', 'action'): 'list',
    ('desk_ops', 'action'): 'tasks',
    ('desk_research', 'action'): 'list',
    ('desk_scan', 'limit'): 20,
    ('desk_strategy_data', 'kind'): 'equity',
    ('desk_history', 'limit'): 200,
    ('desk_local', 'action'): 'list',
    ('desk_close_tabs', 'all'): False,
}


def _param_default(tool: str, key: str, schema: Dict[str, Any]) -> Any:
    """参数默认值：界面上「有默认就填，没有就空串」✓"""
    if (tool, key) in UI_DEFAULTS:
        return UI_DEFAULTS[(tool, key)]
    if isinstance(schema, dict) and 'default' in schema:
        return schema['default']
    return ''


def ui_catalog(names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """给界面（定时任务）用的工具目录：说明 / 参数 / 参数骨架 ✓

    返回 `[{name, description, params:[{name,type,description,default,
    required}], skeleton}]`，`skeleton` 是**可直接粘进参数框**的 JSON 字符串。
    """
    import json as _jsonlib
    wanted = set(names or [])
    rows: List[Dict[str, Any]] = []
    for spec in SPECS:
        block = spec.get('function') or {}
        name = str(block.get('name') or '')
        if not name or (wanted and name not in wanted):
            continue
        params = block.get('parameters') or {}
        props = params.get('properties') or {}
        required = set(params.get('required') or [])
        items = []
        skeleton: Dict[str, Any] = {}
        for key, schema in props.items():
            item = schema if isinstance(schema, dict) else {}
            default = _param_default(name, key, item)
            items.append({'name': key, 'type': str(item.get('type') or ''),
                          'description': str(item.get('description') or ''),
                          'default': default, 'required': key in required})
            skeleton[key] = default
        rows.append({
            'name': name,
            'description': str(block.get('description') or ''),
            'params': items,
            'skeleton': _jsonlib.dumps({'tool': name, 'args': skeleton},
                                       ensure_ascii=False),
        })
    return rows


def _json(payload: Any, limit: int = 20000) -> str:
    """返回**合法** JSON（太长就裁字段，绝不截断字符串本身 ✗）"""
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if len(text) <= limit:
        return text
    text = json.dumps(_clip(payload, 8000), ensure_ascii=False, indent=2)
    if len(text) <= limit:
        return text
    preview = text[:limit - 200]
    return json.dumps({'ok': bool(payload.get('ok', True))
                       if isinstance(payload, dict) else True,
                       'truncated': True, 'preview': preview},
                      ensure_ascii=False)


def _current_symbol(desk) -> str:
    for attr in ('last_symbol', 'symbol'):
        value = str(getattr(desk, attr, '') or '')
        if value:
            return value
    tabs = getattr(desk, 'tabs', {}) or {}
    return str(next(iter(tabs), ''))


def _require(desk) -> bool:
    return desk is not None


# ---------------------------------------------------------------- 分发
def call(name: str, args: Dict[str, Any], desk=None,
         session: str = '') -> str:
    """执行一个 `desk_*` 工具；**任何异常都转成文字**给模型 ✓"""
    key = str(name or '')
    payload = args if isinstance(args, dict) else {}
    if key not in NAMES:
        return f'未知的 desk 工具：{key}（可用：{", ".join(NAMES)}）'
    if not _require(desk):
        return ('当前没有可操控的 desk 窗口（例如在命令行里跑 CI）'
                '：这个工具只在 desk 界面里可用')
    flags_ = flags()
    safe_stop = (key == 'desk_strategy_live'
                 and str(payload.get('action') or 'start').lower() == 'stop')
    # 关掉「允许操控」→ 改界面的工具全部拦下；只读 / 停止不拦 ✓
    if not flags_['allow'] and key not in READONLY and not safe_stop:
        text = _json({'ok': False, 'disabled': True,
                      'detail': '用户在「设置 → PI 操控 desk」里关闭了'
                                '「允许 PI 操控 desk」，现在只能看、不能改。'})
        audit(key, payload, 'disabled', session)
        return text
    # 「停止」是安全动作 → 不受下单开关 / 确认限制 ✓
    if key in ORDER_TOOLS and not safe_stop and not flags_['order']:
        text = _json({'ok': False, 'need_setting': True,
                      'detail': '下单 / 实盘需要用户先在「设置 → PI 操控 desk」'
                                '打开「允许下单 / 策略实盘」（默认是关的）。'})
        audit(key, payload, 'need_setting', session)
        return text
    # 「停止」是安全动作 → 不需要确认（只有 start / 下单要 ✓）
    safe = key == 'desk_strategy_live' and         str(payload.get('action') or 'start').lower() == 'stop'
    if key in DANGEROUS and not safe and not bool(payload.get('confirm')):
        text = _json({'ok': False, 'need_confirm': True,
                      'detail': DANGER_TEXT.get(key, '这个动作需要用户确认'),
                      'args': _redact(payload)})
        audit(key, payload, 'need_confirm', session)
        return text
    handler = globals().get(f'_call_{key[5:]}')
    if handler is None:
        return f'{key} 还没实现（下一阶段会补）'
    try:
        text = handler(desk, payload)
    except Exception as error:                                # noqa: BLE001
        text = f'{key} 失败：{type(error).__name__}: {error}'
    audit(key, payload, text, session)
    return text


# ---------------------------------------------------------------- 只读
#: 常见写法 → desk 目录前缀（模型常写 pandas_ta.macd / ta-lib 等 ✓）
KEY_ALIASES = (
    ('pandas_ta.', 'pta_'), ('pandas-ta.', 'pta_'), ('pandas_ta/', 'pta_'),
    ('pandas-ta/', 'pta_'), ('pandasta.', 'pta_'), ('pandasta/', 'pta_'),
    ('pandas.', 'pta_'), ('pta:', 'pta_'), ('pta.', 'pta_'),
    ('talib.', 'talib_'), ('ta-lib.', 'talib_'), ('talib:', 'talib_'),
    ('tulip.', 'ti_'), ('tulip:', 'ti_'), ('ti.', 'ti_'),
    ('finta.', 'finta_'), ('finta:', 'finta_'),
    ('tqta.', 'tqta_'), ('tqfunc.', 'tqfunc_'), ('pine.', 'pine_'),
    ('tradingview.', 'tv:'), ('tv.', 'tv:'),
)


def _normalize_key(raw: str) -> str:
    """`pandas_ta.macd` → `pta_macd`；`MACD` → `MACD`（原样保留大小写）"""
    text = str(raw or '').strip()
    if not text:
        return ''
    lowered = text.lower()
    for prefix, target in KEY_ALIASES:
        if lowered.startswith(prefix):
            rest = text[len(prefix):]
            return target + rest
    return text


def _catalog_rows() -> List[Dict[str, Any]]:
    try:
        from . import indicator_catalog as _cat
        return list(_cat.catalog())
    except Exception:                                        # noqa: BLE001
        return []


def _personal_rows() -> List[Dict[str, Any]]:
    try:
        from . import personal as _pi
        return [dict(row, group='我的脚本', prefix='pi')
                for row in (_pi.scan('indicator') or [])]
    except Exception:                                        # noqa: BLE001
        return []


def resolve_indicator(raw: str, limit: int = 6) -> Dict[str, Any]:
    """把模型写的指标名解析成**唯一 key**；多义时给候选 ✓"""
    text = str(raw or '').strip()
    if not text:
        return {'key': '', 'candidates': []}
    rows = _catalog_rows() + _personal_rows()
    keys = [str(item.get('key') or '') for item in rows]
    wanted = _normalize_key(text)
    # ① 精确 / 忽略大小写
    for key in keys:
        if key == wanted:
            return {'key': key, 'candidates': []}
    for key in keys:
        if key.lower() == wanted.lower():
            return {'key': key, 'candidates': []}
    # ② `pi:` 开头的个人脚本（按名字后缀匹配 ✓）
    if wanted.startswith('pi:') and wanted not in keys:
        tail = wanted[3:].lower()
        for key in keys:
            if key.startswith('pi:') and key[3:].lower() == tail:
                return {'key': key, 'candidates': []}
    # ③ 唯一包含匹配（`macd` → 有多个 → 给候选，让模型一轮选定 ✓）
    needle = wanted.lower().lstrip('_')
    prefix_hint = ''
    if '_' in wanted:
        prefix_hint, needle = wanted.split('_', 1)
        needle = needle.lower()
    hits = [key for key in keys
            if needle in key.lower() and (not prefix_hint
                                          or key.lower().startswith(
                                              prefix_hint.lower() + '_'))]
    if len(hits) == 1:
        return {'key': hits[0], 'candidates': []}
    # ④ 去掉前缀再试（`pta` → 全部 pta_*）
    if not hits:
        hits = [key for key in keys if needle in key.lower()]
    # ★ 排序：常见库优先（模型常问 pandas_ta / talib），同级短名优先 ✓
    priority = {'pta': 0, 'talib': 1, 'finta': 2, 'pine': 3, 'ti': 4,
                'tqta': 5, 'tqfunc': 6, 'btind': 7, 'tv': 8}

    def rank(key: str):
        prefix = key.split('_', 1)[0].split(':', 1)[0]
        return (priority.get(prefix, 9), len(key), key)

    hits.sort(key=rank)
    return {'key': '', 'candidates': hits[:max(1, int(limit))]}


def _call_status(desk, args: Dict[str, Any]) -> str:
    tabs = getattr(desk, 'tabs', {}) or {}
    rows = []
    for symbol, info in list(tabs.items())[:12]:
        layout = (info or {}).get('layout') or {}
        rows.append({
            'symbol': symbol,
            'layout': f"{layout.get('cols', 1)}x{layout.get('rows', 1)}",
            'cells': [str(cell.get('symbol') or '')
                      for cell in (layout.get('cells') or [])][:6],
            'indicators': [str(item.get('key') or '')
                           for item in ((info or {}).get('indicators') or [])][:12],
        })
    locals_: List[str] = []
    try:
        store = desk.local_store()
        rows_local = store.items() if hasattr(store, 'items') else []
        locals_ = [str(item.get('name') if isinstance(item, dict) else item)
                   for item in (rows_local or [])][:12]
    except Exception:                                        # noqa: BLE001
        locals_ = []
    local_pages = list((getattr(desk, '_local_pages', {}) or {}).keys())
    hints = []
    if rows:
        hints.append('实时图表：desk_add_indicator{key} / desk_set_cycle{cycle} /'
                     ' desk_replay{action:start}')
    if local_pages:
        hints.append('本地图表：desk_add_indicator{key,local:true} / '
                     'desk_set_layout{local:true,symbols:[…]} / '
                     'desk_replay{local:true}')
    hints.append('不确定指标 key → desk_find_indicator{query}（一次选定）')
    hints.append('看行情数据（不用截图）→ desk_market{action:"klines"|'
                 '"indicator"|"summary"}；缩放 → desk_bars{action:"all"|"last"}')
    hints.append('多步任务（查→加→回放）可以一次给 desk_sequence{steps:[…]}')
    trading = {}
    try:
        reader = getattr(desk, 'trading_snapshot', None)
        if callable(reader):
            trading = dict(reader(_current_symbol(desk)) or {})
    except Exception:                                        # noqa: BLE001
        trading = {}
    return _json({
        'ok': True,
        'current_symbol': _current_symbol(desk),
        'trading': {key: trading.get(key) for key in
                    ('ready', 'account', 'key', 'identity', 'labels',
                     'is_real', 'hint')},
        'charts': rows,
        'local_charts': locals_,
        'local_pages': local_pages,
        'pages': len(getattr(desk, 'tabs', {}) or {}),
        'hints': hints,
    })


def _call_find_indicator(desk, args: Dict[str, Any]) -> str:
    """关键词找指标 → 精确 key（模型**先查再加**，别猜 ✓）"""
    query = str(args.get('query') or '').strip()
    if not query:
        return _json({'ok': False, 'error': '需要 query（如 macd / boll / ma）'})
    limit = max(1, min(30, int(args.get('limit') or 10)))
    rows = _catalog_rows() + _personal_rows()
    needle = _normalize_key(query).lower()
    scored = []
    for row in rows:
        key = str(row.get('key') or '')
        lowered = key.lower()
        name = str(row.get('name') or '').lower()
        label = str(row.get('label') or '').lower()
        score = 0
        if lowered == needle:
            score = 100
        elif lowered.startswith(needle):
            score = 80
        elif needle in lowered:
            score = 60
        elif needle in name or needle in label:
            score = 40
        if score:
            scored.append((score, key, row))
    scored.sort(key=lambda item: (-item[0], len(item[1]), item[1]))
    items = []
    for _score, key, row in scored[:limit]:
        items.append({'key': key,
                      'group': str(row.get('group') or ''),
                      'overlap': bool(row.get('overlap')),
                      'params': [str((p or {}).get('name') or '')
                                 for p in (row.get('params') or [])][:6]})
    resolved = resolve_indicator(query, limit)
    return _json({'ok': True, 'query': query,
                  'resolved': resolved.get('key') or '',
                  'candidates': resolved.get('candidates') or [],
                  'count': len(items), 'items': items,
                  'next_hint': '选好后调 desk_add_indicator{key:…}；'
                               '本地图表再加 local:true / page'})

def _call_local_list(desk, args: Dict[str, Any]) -> str:
    store = desk.local_store()
    rows = store.items() if hasattr(store, 'items') else []
    items = []
    for row in rows or []:
        if isinstance(row, dict):
            items.append({'name': str(row.get('name') or ''),
                          'count': row.get('count') or row.get('bars')})
        else:
            items.append({'name': str(row)})
    return _json({'ok': True, 'count': len(items), 'items': items[:40]})


def _book_page(desk, args: Dict[str, Any]) -> str:
    return (str(args.get('page') or '')
            or str(getattr(desk, '_active_local_page', '') or '')
            or f"chart:{_current_symbol(desk)}")


def _call_book(desk, args: Dict[str, Any]) -> str:
    action = str(args.get('action') or 'read').lower()
    # ★ 「打开二级报价」= 让右侧面板显示（以前只有 watch 订阅数据，
    #   面板一直是隐藏的 → 模型只能确认数据，看不到界面 ✗ 用户 2026-11-08）
    if action in ('open', 'show', 'close', 'hide', 'toggle'):
        on = action in ('open', 'show')
        if action == 'toggle':
            on = None
        page = _book_page(desk, args)
        payload = {'type': 'ui_action', 'action': 'book', 'page': page,
                   'symbol': str(args.get('symbol') or '')
                   or _current_symbol(desk)}
        if on is not None:
            payload['on'] = bool(on)
        desk.push(payload)
        return _json({'ok': True, 'page': page,
                      'shown': ('toggle' if on is None else bool(on)),
                      'message': '已' + ('切换' if on is None else
                                        ('打开' if on else '关闭'))
                                 + '右侧二级报价面板'})
    if action in ('watch', 'off') or args.get('on') is not None:
        # on 优先（`desk_book{on:false}` 等价 action=off ✓）
        on = action == 'watch'
        if args.get('on') is not None:
            on = bool(args.get('on'))
        # 按格订阅 / 退订（以前是单独的 desk_book_watch ✓）
        page = str(args.get('page') or '') or str(
            getattr(desk, '_active_local_page', '') or '')             or f"chart:{_current_symbol(desk)}"
        cell = max(0, int(args.get('cell') or 0))
        desk._on_book_watch({'page': page, 'cell': cell, 'on': on,
                             'symbol': str(args.get('symbol') or '')
                             or _current_symbol(desk)})
        shown = None
        # 「打开二级报价」通常是**订阅 + 显示面板**：watch 默认顺手打开 ✓
        if on and args.get('open') is not False:
            desk.push({'type': 'ui_action', 'action': 'book', 'page': page,
                       'on': True})
            shown = True
        return _json({'ok': True, 'page': page, 'cell': cell, 'on': on,
                      'panel_shown': shown,
                      'hint': ('盘口已订阅，右侧面板已打开 ✓' if shown
                               else '盘口已订阅（面板仍按原来的显隐状态）')})
    symbol = str(args.get('symbol') or _current_symbol(desk))
    data = desk.book_payload(symbol, desk.current_feed())
    rows = {
        'symbol': symbol,
        'bids': (data.get('bids') or [])[:5],
        'asks': (data.get('asks') or [])[:5],
        'price': data.get('price') or data.get('last') or 0,
    }
    return _json({'ok': True, **rows})


def _call_drawings(desk, args: Dict[str, Any]) -> str:
    """画线：list 列出 / clear 删除 / toolbox 开关（右键「画线」✓）"""
    action = str(args.get('action') or 'list').lower()
    if action in ('toolbox', 'toggle', 'draw'):
        return _call_draw_toolbox(desk, args)
    if action == 'clear':
        return _call_clear_drawings(desk, args)
    from . import drawings as _drawings
    symbol = str(args.get('symbol') or _current_symbol(desk))
    found = {}
    for key, items in (_drawings.all_drawings() or {}).items():
        if not symbol or str(key).startswith(symbol):
            found[str(key)] = items[:20]
    return _json({'ok': True, 'symbol': symbol,
                  'keys': list(found)[:10], 'drawings': found})


# ---------------------------------------------------------------- 界面操作
def _call_switch_symbol(desk, args: Dict[str, Any]) -> str:
    symbol = str(args.get('symbol') or '').strip()
    if not symbol:
        return 'desk_switch_symbol 需要一个合约代码，例如 DCE.a2701'
    cell = max(0, int(args.get('cell') or 0))
    local = bool(args.get('local'))
    names = {str(item.get('name') if isinstance(item, dict) else item)
             for item in (_call_store_items(desk))}
    if local and symbol in names:
        # ★ 本地图表切的是**数据集**（CSV）→ 走 `local_switch` ✓
        #   （`switch_symbol` 要连行情源取 K 线，CSV 名会失败 ✗）
        desk._on_local_switch({'from': _current_symbol(desk), 'to': symbol,
                               'cell': cell,
                               'page': str(args.get('page') or '')})
        return _json({'ok': True, 'switched': symbol, 'cell': cell,
                      'local': True})
    desk._on_switch_symbol({'from': _current_symbol(desk), 'to': symbol,
                            'cell': cell, 'local': local})
    return _json({'ok': True, 'switched': symbol, 'cell': cell})


def _call_add_indicator(desk, args: Dict[str, Any]) -> str:
    raw_key = str(args.get('key') or '').strip()
    if not raw_key:
        return _json({'ok': False,
                      'error': '需要 key（如 MACD / pta_macd；不确定先用 '
                               'desk_find_indicator）'})
    # ★ 自动解析别名（`pandas_ta.macd` → `pta_macd`），多义就给候选 ✓
    resolved = resolve_indicator(raw_key)
    if not resolved.get('key'):
        return _json({'ok': False, 'need_key_choice': True,
                      'query': raw_key,
                      'candidates': resolved.get('candidates') or [],
                      'next_hint': '从 candidates 里挑一个精确 key，再调一次 '
                                   'desk_add_indicator（一轮就能定 ✓）'})
    key = str(resolved['key'])
    local = bool(args.get('local')) or bool(args.get('page'))
    symbol = (_local_symbol(desk, args) if local
              else (str(args.get('symbol') or '') or _current_symbol(desk)))
    cell = max(0, int(args.get('cell') or 0))
    params = args.get('params') if isinstance(args.get('params'), dict) else {}
    if local:
        ok = desk._on_local_add_indicator({'symbol': symbol, 'key': key,
                                           'cell': cell, 'params': params,
                                           'page': _active_page(desk, args)})
    else:
        ok = desk._on_add_indicator({'symbol': symbol, 'key': key,
                                     'cell': cell, 'params': params})
    return _json({'ok': bool(ok), 'symbol': symbol, 'key': key,
                  'cell': cell,
                  'message': '已加指标' if ok else '没加上（看运行日志 / 弹窗）',
                  'next_hint': ('要回放：desk_replay{local:true, name/symbol}；'
                                '要删：desk_remove_indicator{key}')
                  if ok else '可以换一个 key（desk_find_indicator）'})


def _call_remove_indicator(desk, args: Dict[str, Any]) -> str:
    key = str(args.get('key') or '').strip()
    if not key:
        return 'desk_remove_indicator 需要一个指标 key'
    local = bool(args.get('local')) or bool(args.get('page'))
    symbol = (_local_symbol(desk, args) if local
              else (str(args.get('symbol') or '') or _current_symbol(desk)))
    cell = max(0, int(args.get('cell') or 0))
    if local:
        desk._on_local_remove_indicator({'symbol': symbol, 'key': key,
                                         'cell': cell,
                                         'page': _active_page(desk, args)})
    else:
        desk._on_remove_indicator({'symbol': symbol, 'key': key,
                                   'cell': cell})
    return _json({'ok': True, 'symbol': symbol, 'key': key})


def _call_set_layout(desk, args: Dict[str, Any]) -> str:
    symbols = [str(item) for item in (args.get('symbols') or [])
               if str(item)]
    local = bool(args.get('local')) or bool(symbols)
    if local:
        # ★ 本地图表：按数据集逐格组布局（以前只调 set_layout → 没反应 ✗）
        if not symbols:
            return _json({'ok': False,
                          'error': '本地布局需要 symbols（每格的 CSV 名），'
                                   '例如 ["test","l2609_60"]'})
        cols = max(1, min(3, int(args.get('cols') or 0)
                          or (2 if len(symbols) >= 2 else 1)))
        rows = max(1, min(2, int(args.get('rows') or 0)
                          or (2 if len(symbols) >= 3 else 1)))
        desk._on_local_layout({'symbols': symbols, 'cols': cols,
                               'rows': rows,
                               'page': _active_page(desk, args)})
        return _json({'ok': True, 'local': True, 'symbols': symbols,
                      'layout': f'{cols}x{rows}'})
    cols = max(1, min(3, int(args.get('cols') or 1)))
    rows = max(1, min(2, int(args.get('rows') or 1)))
    symbol = str(args.get('symbol') or '') or _current_symbol(desk)
    desk._on_set_layout({'symbol': symbol, 'cols': cols, 'rows': rows})
    return _json({'ok': True, 'symbol': symbol, 'layout': f'{cols}x{rows}'})


def _local_symbol(desk, args: Dict[str, Any]) -> str:
    """本地图表当前格的数据集名（没传 symbol 时自动取 ✓）"""
    page = _active_page(desk, args)
    cell = max(0, int(args.get('cell') or 0))
    pages = getattr(desk, '_local_pages', {}) or {}
    mapping = pages.get(page) or {}
    name = str(args.get('symbol') or '') or str(mapping.get(cell) or '')
    if not name:
        name = str((mapping.values().__iter__().__next__()
                    if mapping else ''))
    if not name:
        names = getattr(desk, '_local_cell_names', {}) or {}
        name = str(names.get(cell) or '')
    return name


def _active_page(desk, args: Dict[str, Any]) -> str:
    """没有显式 `page` → 用「当前活动的本地图表页」（工具调用常见 ✓）"""
    page = str(args.get('page') or '')
    if page:
        return page
    return str(getattr(desk, '_active_local_page', '') or '')


def _call_store_items(desk) -> List[Any]:
    try:
        store = desk.local_store()
        return list(store.items() if hasattr(store, 'items') else [])
    except Exception:                                        # noqa: BLE001
        return []


def _call_local_pages(desk, args: Dict[str, Any]) -> str:
    pages = getattr(desk, '_local_pages', {}) or {}
    rows = []
    for page, cells in pages.items():
        rows.append({'page': str(page),
                     'cells': {str(index): str(name)
                               for index, name in (cells or {}).items()}})
    return _json({'ok': True, 'active': str(getattr(
        desk, '_active_local_page', '') or ''), 'pages': rows})


def _call_clear_indicators(desk, args: Dict[str, Any]) -> str:
    local = bool(args.get('local')) or bool(args.get('page'))
    symbol = (_local_symbol(desk, args) if local
              else (str(args.get('symbol') or '') or _current_symbol(desk)))
    cell = max(0, int(args.get('cell') or 0))
    page = _active_page(desk, args)
    removed: List[str] = []
    if local:
        items = desk._local_items(symbol, cell, page) if hasattr(
            desk, '_local_items') else []
        for item in items:
            key = str((item or {}).get('key') or '')
            if not key:
                continue
            desk._on_local_remove_indicator({'symbol': symbol, 'key': key,
                                             'cell': cell, 'page': page})
            removed.append(key)
    else:
        info = (getattr(desk, 'tabs', {}) or {}).get(symbol) or {}
        for item in list(info.get('indicators') or []):
            key = str((item or {}).get('key') or '')
            if not key:
                continue
            desk._on_remove_indicator({'symbol': symbol, 'key': key,
                                       'cell': cell})
            removed.append(key)
    return _json({'ok': True, 'symbol': symbol, 'cell': cell,
                  'removed': removed, 'count': len(removed)})


def _call_clear_drawings(desk, args: Dict[str, Any]) -> str:
    symbol = str(args.get('symbol') or '') or _current_symbol(desk)
    cycle = int(args.get('cycle') or 60)
    if not symbol:
        return _json({'ok': False, 'error': '需要 symbol（合约代码）'})
    key = f'{symbol}|{cycle}'
    desk._on_clear_drawings({'key': key})
    return _json({'ok': True, 'key': key})


def _call_local_load(desk, args: Dict[str, Any]) -> str:
    name = str(args.get('name') or '').strip()
    if not name:
        return 'desk_local_load 需要数据集名字（先用 desk_local_list 看看）'
    desk._on_local_load({'name': name})
    audit('desk_local_load', {'name': name}, name)
    return _json({'ok': True, 'loaded': name,
                  'message': '已加载（本地图表页会立刻打开）'})



# ---------------------------------------------------------------- 页面 / 回测
def _call_open_page(desk, args: Dict[str, Any]) -> str:
    """打开页面：本地图表 / 实时图表 / 策略回测 / 参数优化 ✓"""
    kind = str(args.get('kind') or '').lower()
    if kind in ('local', 'local_chart'):
        name = str(args.get('name') or '')
        desk.queue_ui('open_local_chart', name=name)
        return _json({'ok': True, 'opened': 'local_chart', 'name': name})
    if kind in ('chart', 'watch', 'realtime'):
        symbol = str(args.get('symbol') or '') or _current_symbol(desk)
        if not symbol:
            return 'desk_open_page 打开图表需要合约代码（symbol）'
        desk.queue_ui('open_chart', symbol=symbol)
        return _json({'ok': True, 'opened': 'chart', 'symbol': symbol})
    if kind in ('home', 'quote', 'settings', 'logs', 'palette',
                'workspace', 'research'):
        # ★ 这些是**前端页面**：用 ui_action 打开（不用 queue_ui ✓）
        desk.push({'type': 'ui_action', 'action': 'open_ui',
                   'target': kind})
        return _json({'ok': True, 'opened': kind})
    if kind in ('backtest', 'optimize', 'strategy_lab'):
        path = str(args.get('file') or '')
        if not path:
            return '打开策略回测 / 参数优化需要 file（.py 路径）'
        mode = 'optimize' if kind == 'optimize' else 'backtest'
        desk.queue_ui('open_strategy_lab', file=path, mode=mode)
        return _json({'ok': True, 'opened': mode, 'file': path})
    return _json({'ok': False,
                  'error': 'kind 只能是 local_chart / chart / backtest / '
                           'optimize / home / quote / settings / logs / '
                           f'palette（收到 {kind or "空"}）'})


def _call_backtest_run(desk, args: Dict[str, Any]) -> str:
    """跑策略回测（后台线程，结果用 desk_strategy_status 看 ✓）"""
    return _run_strategy(desk, args, 'backtest')


def _call_optimize_run(desk, args: Dict[str, Any]) -> str:
    """跑参数优化（同上）"""
    return _run_strategy(desk, args, 'optimize')


def _run_strategy(desk, args: Dict[str, Any], mode: str) -> str:
    path = str(args.get('file') or '').strip()
    if not path:
        return '需要 file：策略 .py 的完整路径'
    if not os.path.isfile(path):
        return f'策略文件不存在：{path}'
    if not path.lower().endswith('.py'):
        return '只支持 .py 策略文件'
    params = args.get('params') if isinstance(args.get('params'), dict) else {}
    options = args.get('options') if isinstance(args.get('options'), dict) else {}
    targets = args.get('targets') or args.get('metrics') or []
    symbol = str(args.get('symbol') or '')
    if symbol:
        desk.queue_ui('open_chart', symbol=symbol)
    desk.queue_ui('open_strategy_lab', file=path, mode=mode)
    desk._on_strategy_start({'file': path, 'mode': mode, 'params': params,
                             'options': options,
                             'targets': targets if isinstance(targets, list)
                             else [],
                             'symbol': symbol})
    return _json({'ok': True, 'mode': mode, 'file': path,
                  'message': '已开始（结果会在「策略回测 / 参数优化」页出现）'})


def _call_strategy_status(desk, args: Dict[str, Any]) -> str:
    labs = getattr(desk, '_strategy_labs', {}) or {}
    rows = []
    for key, lab in list(labs.items())[-5:]:
        rows.append({
            'id': str(key),
            'file': os.path.basename(str(getattr(lab, 'file', '') or '')),
            'mode': str(getattr(lab, 'mode', '') or ''),
            'running': bool(getattr(lab, '_thread', None)
                            and lab._thread.is_alive()),
        })
    live = []
    try:
        for key, item in (desk._live_map() or {}).items():
            live.append({'file': os.path.basename(str(key)),
                         'running': bool(getattr(item, 'running', False))})
    except Exception:                                        # noqa: BLE001
        live = []
    return _json({'ok': True, 'sessions': rows, 'live': live})


# ---------------------------------------------------------------- 账户（只读）
def _trading_state(desk, symbol: str = '') -> Dict[str, Any]:
    """交易登录 / 账户状态（老 desk 没有 `trading_snapshot` → 未知 ✓）"""
    reader = getattr(desk, 'trading_snapshot', None)
    if callable(reader):
        try:
            data = reader(symbol)
            return dict(data or {})
        except Exception:                                    # noqa: BLE001
            return {}
    return {'ready': None}


def _account_rows(desk, local: bool = False, key: str = '',
                  symbol: str = '') -> Dict[str, Any]:
    """持仓 / 委托 / 成交 / 资金快照（本地模拟 or 真实账户 ✓）

    ★ 用户 2026-11-08：模型查账户「什么都读不到」。根因是这里拿
      `trader.positions` / `trader.orders` —— `Trading` 上**根本没有**这两个
      属性（真正实现是 `Desk.account_view()`）→ 恒回空列表 ✗。
      现在走 `AccountView.tables()` / `summary()`（和底部账户面板同一套 ✓）。
    """
    symbol = str(symbol or '') or _current_symbol(desk)
    state = _trading_state(desk, symbol)
    rows: Dict[str, Any] = {
        'ok': True, 'source': 'real', 'symbol': symbol,
        'login': state, 'account': str(state.get('account') or ''),
        'labels': list(state.get('labels') or []),
        'balance': dict(state.get('balance') or {}),
        'positions': {}, 'orders': {}, 'unfilled': {}, 'trades': {},
    }
    if local:
        sim = desk.local_sim()
        symbol = _current_symbol(desk)
        data = sim.payload(symbol) if hasattr(sim, 'payload') else {}

        tables = data.get('tables') or {}

        def table(key: str) -> Dict[str, Any]:
            block = tables.get(key) or data.get(key)
            if isinstance(block, dict):
                return {'columns': block.get('columns') or [],
                        'rows': (block.get('rows') or [])[:50]}
            return {'columns': [], 'rows': list(block or [])[:50]}

        rows['source'] = 'local'
        rows['positions'] = table('positions')
        rows['orders'] = table('orders')
        rows['unfilled'] = table('orders')
        rows['trades'] = table('trades')
        rows['balance'] = {'balance': (data.get('values') or {})
                           .get('balance') or 0}
        rows['account'] = '本地模拟'
        return rows
    view = desk.account_view() if hasattr(desk, 'account_view') else None
    if view is None:
        rows['ok'] = False
        rows['message'] = '交易未连接（先登录期货账户）'
        return rows
    try:
        tables = view.tables(limit=100, symbol=symbol, key=key) or {}
    except Exception as error:                                # noqa: BLE001
        rows['ok'] = False
        rows['message'] = f'读账户数据失败：{type(error).__name__}: {error}'
        return rows
    if not tables:
        rows['ok'] = False
        rows['message'] = ('账户接口还没就绪（登录中 / 交易未连接）：'
                           '先 desk_login_futures 登录后再查')
        return rows
    for name in ('positions', 'orders', 'unfilled', 'trades'):
        block = tables.get(name) or {}
        rows[name] = {'columns': list(block.get('columns') or []),
                      'rows': list(block.get('rows') or [])[:100]}
    try:
        summary = view.summary(symbol, key) or {}
    except Exception:                                        # noqa: BLE001
        summary = {}
    if summary:
        rows['balance'] = dict(summary.get('values') or rows['balance'])
        rows['account'] = str(summary.get('label') or rows['account'])
        rows['labels'] = list(summary.get('labels') or rows['labels'])
    return rows


def _account_args(desk, args: Dict[str, Any]) -> Dict[str, Any]:
    return {'local': bool(args.get('local')),
            'key': str(args.get('key') or ''),
            'symbol': str(args.get('symbol') or '') or _current_symbol(desk)}


def _call_positions(desk, args: Dict[str, Any]) -> str:
    data = _account_rows(desk, **_account_args(desk, args))
    return _json({'ok': data.get('ok'), 'source': data.get('source'),
                  'symbol': data.get('symbol'),
                  'account': data.get('account', ''),
                  'login': data.get('login'),
                  'positions': data.get('positions'),
                  'message': data.get('message', '')})


def _call_orders(desk, args: Dict[str, Any]) -> str:
    data = _account_rows(desk, **_account_args(desk, args))
    return _json({'ok': data.get('ok'), 'source': data.get('source'),
                  'symbol': data.get('symbol'),
                  'account': data.get('account', ''),
                  'login': data.get('login'),
                  'orders': data.get('orders'),
                  'message': data.get('message', '')})


# ---------------------------------------------------------------- 下单
def _call_order(desk, args: Dict[str, Any]) -> str:
    """只允许**限价单**；平今 / 平昨由 offset 决定（沿用既有约束 ✓）

    ★ 用户 2026-11-08 实测：没登录交易时也回「已提交」→ 审计 5 单全是
      `PENDING`、`account` 空、柜台里根本没有这 5 笔。现在两处兜底：
      1. **预检** `desk.trading_snapshot()`：没就绪 → `need_login`，不下单；
      2. 提交后看 `_on_place_order()` 的**真实回执文本**：`未启用 / 未连接 /
         失败 / 没有可平…` 一律 `ok:false`，并把账户名 + 下一步回给模型 ✓
    """
    symbol = str(args.get('symbol') or '').strip()
    side = str(args.get('side') or '').lower()
    volume = int(args.get('volume') or 0)
    price = float(args.get('price') or 0)
    offset = str(args.get('offset') or 'open').lower()
    errors = []
    if not symbol:
        errors.append('需要 symbol（合约代码）')
    if side not in ('buy', 'sell'):
        errors.append('side 只能是 buy / sell')
    if volume <= 0:
        errors.append('volume 必须是正整数')
    if price <= 0:
        errors.append('只允许限价单：price 必须 > 0（不支持下市价单）')
    if offset not in ('open', 'close', 'close_today', 'close_yesterday'):
        errors.append('offset 只能是 open / close（平今平昨由接口自动拆 ✓）')
    if errors:
        return _json({'ok': False, 'error': '；'.join(errors)})
    payload = {'symbol': symbol, 'side': side, 'volume': volume,
               'price': price, 'offset': 'close' if offset.startswith('close')
               else 'open'}
    if args.get('local'):
        desk._on_local_order({**payload, 'close': offset.startswith('close')})
        return _json({'ok': True, 'source': 'local', 'symbol': symbol,
                      'side': side, 'volume': volume, 'price': price,
                      'offset': offset, 'account': '本地模拟',
                      'message': '已提交到本地模拟账户'})
    state = _trading_state(desk, symbol)
    if state.get('ready') is False:
        return _json({'ok': False, 'need_login': True, 'submitted': False,
                      'error': '交易未连接 / 未登录，这笔委托**没有提交**',
                      'login': state, 'symbol': symbol,
                      'hint': state.get('hint')
                      or '先 desk_login_futures 登录天勤（或用 local:true 在'
                         '本地模拟账户下单）'})
    text = ''
    try:
        text = str(desk._on_place_order({**payload, 'account': str(
            args.get('account') or '')}) or '')
    except Exception as error:                                # noqa: BLE001
        return _json({'ok': False, 'submitted': False, 'symbol': symbol,
                      'error': f'下单调用出错：{type(error).__name__}: {error}'})
    from .trading import _trade_failed
    failed = bool(text) and _trade_failed(text)
    result: Dict[str, Any] = {
        'ok': not failed, 'submitted': bool(text) and not failed,
        'text': text, 'symbol': symbol, 'side': side, 'volume': volume,
        'price': price, 'offset': offset,
        'account': str(state.get('account') or '') or '当前账户',
    }
    if failed:
        result['error'] = text
    else:
        result['next_hint'] = ('用 desk_account{action:"unfilled"} 核对有没有'
                               '挂上；审计里的 PENDING 只是「已提交给柜台」，'
                               '不代表成交 ✓')
    return _json(result)


# ---------------------------------------------------------------- 策略实盘
def _call_strategy_live(desk, args: Dict[str, Any]) -> str:
    action = str(args.get('action') or 'start').lower()
    path = str(args.get('file') or '').strip()
    if not path:
        return '需要 file：策略 .py 的完整路径'
    if action == 'stop':
        desk._on_strategy_live_stop({'file': path})
        return _json({'ok': True, 'stopped': path})
    desk._on_strategy_live_start({'file': path, 'confirm': True})
    return _json({'ok': True, 'started': path,
                  'message': '已启动（注意：会真实下单，随时可 stop）'})


# ---------------------------------------------------------------- 工具栏（A 批）
def _supported_cycles() -> tuple:
    try:
        from .app import Desk as _Desk
        return tuple(_Desk.CYCLES_SUPPORTED)
    except Exception:                                        # noqa: BLE001
        return (1, 5, 15, 30, 60, 180, 300, 900, 1800, 2700, 3600, 7200,
                14400, 86400, 172800, 259200, 604800, 2592000)


def _call_set_cycle(desk, args: Dict[str, Any]) -> str:
    """切周期（按格；实时图表 / 本地图表都支持 ✓）

    ★ 用户 2026-11-08：「请将白银切换为 5 分钟周期」→ 模型传 `cycle: 5`
      被当成 **5 秒** → 天勤不支持 → 空 K 线 → 图表被清空，看起来"没切成功" ✗。
      现在：认 `300` / `'300'` / `'5m'` / `'5分钟'` / `'1h'`，**先校验**再动手，
      并把真正生效的周期（`cycle` + 中文 `label`）回给模型核对 ✓
    """
    symbol = str(args.get('symbol') or '') or _current_symbol(desk)
    cell = max(0, int(args.get('cell') or 0))
    raw = args.get('cycle')
    normalized = 0
    resolver = getattr(desk, 'normalize_cycle', None)
    if callable(resolver):
        try:
            normalized = int(resolver(raw) or 0)
        except Exception:                                    # noqa: BLE001
            normalized = 0
    else:
        # ★ 没有 `normalize_cycle` 的 desk（测试替身 / 老版本）也要认
        #   `'5m'` / `'5分钟'` 这类写法 —— 直接复用 Desk 的解析器 ✓
        try:
            from .app import Desk as _Desk
            normalized = int(_Desk.normalize_cycle(raw) or 0)
        except Exception:                                    # noqa: BLE001
            try:
                normalized = int(raw)
            except (TypeError, ValueError):
                normalized = 0
    if normalized <= 0:
        return _json({'ok': False,
                      'error': f'不支持的周期：{raw!r}',
                      'hint': '周期单位是**秒**：5 分钟 = 300；也可以写 '
                              '"5m" / "5分钟" / "1h" / "1d"',
                      'supported': list(getattr(desk, 'CYCLES_SUPPORTED', ())
                                        or _supported_cycles())})
    setter = getattr(desk, 'set_cycle', None)
    if callable(setter):
        try:
            result = dict(setter(symbol, normalized, cell) or {})
        except Exception as error:                            # noqa: BLE001
            return _json({'ok': False, 'symbol': symbol,
                          'error': f'切周期失败：{type(error).__name__}: {error}'})
        if not result.get('ok'):
            return _json(result)
        return _json({'ok': True, 'symbol': result.get('symbol') or symbol,
                      'cycle': normalized,
                      'label': result.get('label', str(normalized)),
                      'cell': cell, 'hint': result.get('hint', '')})
    desk._on_set_cycle({'symbol': symbol, 'cycle': normalized, 'cell': cell})
    return _json({'ok': True, 'symbol': symbol, 'cycle': normalized,
                  'cell': cell})


def _call_open_chart(desk, args: Dict[str, Any]) -> str:
    symbol = str(args.get('symbol') or '') or _current_symbol(desk)
    if not symbol:
        return _json({'ok': False, 'error': '需要 symbol（合约代码）'})
    desk._on_open_chart({'symbol': symbol})
    return _json({'ok': True, 'opened': symbol})


def _call_close_chart(desk, args: Dict[str, Any]) -> str:
    symbol = str(args.get('symbol') or '') or _current_symbol(desk)
    if not symbol:
        return _json({'ok': False, 'error': '需要 symbol（合约代码）'})
    desk._on_close_chart({'symbol': symbol})
    return _json({'ok': True, 'closed': symbol})


def _call_replay(desk, args: Dict[str, Any]) -> str:
    """回放：`action=start` 进入 / `exit` 退出（本地图表要 `local:true` ✓）"""
    action = str(args.get('action') or 'start').lower()
    if args.get('local'):
        # ★ 本地图表的回放是**前端动作**（`toggleReplay`）→ 用 ui_action ✓
        page = _active_page(desk, args)
        desk.push({'type': 'ui_action', 'action': 'replay', 'page': page,
                   'name': str(args.get('name') or args.get('symbol') or ''),
                   'count': int(args.get('count') or 0)})
        return _json({'ok': True, 'action': action, 'local': True,
                      'page': page,
                      'next_hint': '回放里下单用 desk_replay_trade{action:order,…}'})
    symbol = str(args.get('symbol') or '') or _current_symbol(desk)
    if action == 'exit':
        try:
            desk._on_replay_exit({'symbol': symbol})
        except Exception as error:                            # noqa: BLE001
            return _json({'ok': False, 'action': 'exit',
                          'error': f'退出回放失败（没有行情源？）：{error}'})
        return _json({'ok': True, 'action': 'exit', 'symbol': symbol})
    payload = {'symbol': symbol}
    for key in ('cycle', 'count'):
        if args.get(key) is not None:
            payload[key] = args.get(key)
    desk._on_replay(payload)
    return _json({'ok': True, 'action': 'start', 'symbol': symbol,
                  'cycle': payload.get('cycle'),
                  'count': payload.get('count')})


def _call_indicator_picker(desk, args: Dict[str, Any]) -> str:
    """打开指标选择器（让**用户**自己挑，不是模型加 ✓）"""
    symbol = str(args.get('symbol') or '') or _current_symbol(desk)
    payload = {'symbol': symbol, 'cell': max(0, int(args.get('cell') or 0))}
    if args.get('local'):
        payload['local'] = True
        page = _active_page(desk, args)
        if page:
            payload['page'] = page
    desk._on_indicator_picker(payload)
    return _json({'ok': True, 'opened': 'indicator_picker',
                  'symbol': symbol})


def _call_templates(desk, args: Dict[str, Any]) -> str:
    """列出已保存的指标模板（只读 ✓）"""
    from . import user_prefs as _prefs
    rows = [{'key': item.get('key'), 'name': item.get('name'),
             'count': len(item.get('items') or [])}
            for item in _prefs.templates()]
    rows.sort(key=lambda row: str(row.get('name') or '').lower())
    return _json({'ok': True, 'count': len(rows), 'items': rows[:40]})


def _call_apply_template(desk, args: Dict[str, Any]) -> str:
    key = str(args.get('key') or '').strip()
    if not key:
        return _json({'ok': False, 'error': '需要 key（先用 desk_templates 看）'})
    symbol = str(args.get('symbol') or '') or _current_symbol(desk)
    payload = {'key': key, 'symbol': symbol,
               'cell': max(0, int(args.get('cell') or 0)),
               'params': args.get('params') if isinstance(
                   args.get('params'), dict) else {}}
    if args.get('local'):
        payload['local'] = True
        payload['page'] = _active_page(desk, args)
    desk._on_apply_template(payload)
    return _json({'ok': True, 'applied': key, 'symbol': symbol})


def _call_save_template(desk, args: Dict[str, Any]) -> str:
    name = str(args.get('name') or '').strip()
    symbol = str(args.get('symbol') or '') or _current_symbol(desk)
    payload = {'name': name, 'symbol': symbol,
               'cell': max(0, int(args.get('cell') or 0))}
    if args.get('local'):
        payload['local'] = True
        payload['page'] = _active_page(desk, args)
    desk._on_save_template(payload)
    return _json({'ok': True, 'saved': name or '(自动命名)',
                  'symbol': symbol})


def _call_layouts(desk, args: Dict[str, Any]) -> str:
    """布局单一入口：list / apply / save / delete / favorite / export ✓

    以前是 6 个独立工具（模型要在里面挑）→ 合并成一个 `action`，
    工具总数 -5，选错概率明显下降 ✓
    """
    from . import user_prefs as _prefs
    action = str(args.get('action') or 'list').lower()
    base = dict(args)
    base.pop('action', None)
    if action in ('list', ''):
        local = bool(args.get('local'))
        scope = 'local' if local else 'realtime'
        rows = [{'key': item.get('key'), 'name': item.get('name'),
                 'cells': len(item.get('cells') or []),
                 'cols': item.get('cols'), 'rows': item.get('rows')}
                for item in _prefs.layouts(scope)]
        return _json({'ok': True, 'scope': scope, 'count': len(rows),
                      'items': rows[:40],
                      'next_hint': '应用：desk_layouts{action:"apply", key}；'
                                   '保存：desk_layouts{action:"save", name}'})
    if action == 'apply':
        return _call_layout_apply(desk, base)
    if action == 'save':
        return _call_layout_save(desk, base)
    if action == 'delete':
        return _call_layout_delete(desk, base)
    if action == 'favorite':
        return _call_layout_favorite(desk, base)
    if action == 'export':
        return _call_layouts_export(desk, base)
    return _json({'ok': False,
                  'error': 'action 只能是 list / apply / save / delete / '
                           'favorite / export'})


def _call_layout_apply(desk, args: Dict[str, Any]) -> str:
    key = str(args.get('key') or '').strip()
    if not key:
        return _json({'ok': False, 'error': '需要 key（先用 desk_layouts 看）'})
    payload = {'key': key, 'symbol': str(args.get('symbol') or '')
               or _current_symbol(desk)}
    if args.get('local'):
        payload['local'] = True
    desk._on_layout_apply(payload)
    return _json({'ok': True, 'applied': key})


def _call_editor_add_indicator(desk, args: Dict[str, Any]) -> str:
    """把**文件里**的指标 / 策略加到图表（编辑器「加到图表」同一条 ✓）"""
    path = str(args.get('path') or '').strip()
    if not path or not os.path.isfile(path):
        return _json({'ok': False, 'error': f'文件不存在：{path}'})
    payload = {'path': path,
               'symbol': str(args.get('symbol') or '') or _current_symbol(desk),
               'cell': max(0, int(args.get('cell') or 0))}
    if args.get('local'):
        payload['local'] = True
        payload['page'] = _active_page(desk, args)
    if args.get('overlay'):
        payload['overlay'] = True
    desk._on_editor_add_indicator(payload)
    return _json({'ok': True, 'added': os.path.basename(path),
                  'symbol': payload['symbol'],
                  'overlay': bool(args.get('overlay'))})


def _call_book_watch(desk, args: Dict[str, Any]) -> str:
    """某格买卖盘 👁 开 / 关（按格订阅，省订阅数 ✓）"""
    page = str(args.get('page') or '') or str(
        getattr(desk, '_active_local_page', '') or '') \
        or f"chart:{_current_symbol(desk)}"
    cell = max(0, int(args.get('cell') or 0))
    on = args.get('on') is not False
    desk._on_book_watch({'page': page, 'cell': cell, 'on': on,
                         'symbol': str(args.get('symbol') or '')
                         or _current_symbol(desk)})
    return _json({'ok': True, 'page': page, 'cell': cell, 'on': on})


# ---------------------------------------------------------------- 编辑器 / 资源管理器（B 批）
def _call_editor_open(desk, args: Dict[str, Any]) -> str:
    path = str(args.get('path') or '').strip()
    if not path:
        return _json({'ok': False, 'error': '需要 path（文件完整路径）'})
    desk._on_editor_open({'path': path})
    return _json({'ok': True, 'opened': path})


def _call_editor_save(desk, args: Dict[str, Any]) -> str:
    """保存源码（不传 text = 只保存已打开的内容 → 这里要求传 text ✓）"""
    path = str(args.get('path') or '').strip()
    text = args.get('text')
    if not path:
        return _json({'ok': False, 'error': '需要 path'})
    if text is None:
        return _json({'ok': False,
                      'error': '需要 text（要写入的完整源码）；'
                               '只想读文件请用 read_file'})
    desk._on_editor_save({'path': path, 'text': str(text),
                          'format': bool(args.get('format'))})
    # ★ 写完**回读校验**（不要「返回 ok 但根本没写」✗）
    try:
        written = read_text_smart(path)
    except OSError as error:
        return _json({'ok': False, 'error': f'写入后读不到：{error}'})
    if not os.path.isfile(path) or not written:
        return _json({'ok': False, 'error': '保存失败（文件没写进去）'})
    return _json({'ok': True, 'saved': path, 'bytes': len(written.encode())})


def _call_editor_new(desk, args: Dict[str, Any]) -> str:
    """按模板新建指标 / 策略（名字给空 = 后端自动命名 ✓）"""
    kind = 'strategy' if str(args.get('kind') or '') == 'strategy' \
        else 'indicator'
    name = str(args.get('name') or '').strip()
    desk._on_editor_new({'kind': kind, 'name': name,
                         'overwrite': bool(args.get('overwrite'))})
    # ★ 回读校验：看个人目录里有没有新文件（没建出来就报错 ✓）
    created = ''
    try:
        from . import personal as _pi
        rows = _pi.scan(kind) or []
        for row in rows:
            row_name = str((row or {}).get('name') or '')
            row_path = str((row or {}).get('path') or '')
            if name and (row_name == name
                         or os.path.splitext(os.path.basename(row_path))[0]
                         == name):
                created = row_path
                break
        if not created and rows and not name:
            created = str((rows[-1] or {}).get('path') or '')
    except Exception:                                        # noqa: BLE001
        created = ''
    if name and not created:
        return _json({'ok': False,
                      'error': f'没建出来：{name}（看运行日志里的报错）'})
    return _json({'ok': True, 'kind': kind, 'name': name or '(自动命名)',
                  'path': created,
                  'message': '已按模板创建（记得改完保存 ✓）'})


def _call_editor_delete(desk, args: Dict[str, Any]) -> str:
    path = str(args.get('path') or '').strip()
    if not path:
        return _json({'ok': False, 'error': '需要 path'})
    desk._on_editor_delete({'path': path})
    if os.path.exists(path):
        # ★ 后端只允许删个人指标 / 策略目录里的文件（别的目录会被拒）
        return _json({'ok': False,
                      'error': f'没有删掉：{path}（desk 只删「我的指标 / '
                               '我的策略」目录里的文件）'})
    return _json({'ok': True, 'deleted': path})


def _call_editor_check(desk, args: Dict[str, Any]) -> str:
    """语法检查（不写盘；直接返回结果 ✓）"""
    path = str(args.get('path') or '')
    text = args.get('text')
    if text is None:
        if not path or not os.path.isfile(path):
            return _json({'ok': False, 'error': '需要 path（存在的文件）或 text'})
        try:
            text = read_text_smart(path)
        except Exception as error:                            # noqa: BLE001
            return _json({'ok': False, 'error': f'读文件失败：{error}'})
    from . import personal as _pi
    result = _pi.check_source(str(text), path or '<editor>')
    return _json({'ok': bool(result.get('ok')), 'path': path,
                  'result': result})


def _call_explorer_set_root(desk, args: Dict[str, Any]) -> str:
    """切资源管理器根目录（= 用户给的任意目录 ✓）"""
    path = str(args.get('path') or '').strip()
    if not path:
        return _json({'ok': False, 'error': '需要 path'})
    if not os.path.isdir(path):
        return _json({'ok': False, 'error': f'目录不存在：{path}'})
    desk._apply_explorer_root(path)
    return _json({'ok': True, 'root': path})


def _call_explorer_system_dir(desk, args: Dict[str, Any]) -> str:
    """切到系统目录：个人指标 / 个人策略 / 两者根目录 ✓"""
    kind = str(args.get('kind') or 'indicator').lower()
    if kind not in ('indicator', 'strategy', 'all'):
        return _json({'ok': False,
                      'error': 'kind 只能是 indicator / strategy / all'})
    desk._on_explorer_system_dir({'kind': kind})
    return _json({'ok': True, 'kind': kind})


def _call_explorer_op(desk, args: Dict[str, Any]) -> str:
    """资源管理器右键操作：新建文件 / 新建文件夹 / 重命名 / 删除 / 复制 / 粘贴"""
    action = str(args.get('action') or '').lower()
    allowed = {'new_file', 'new_folder', 'rename', 'delete', 'copy', 'cut',
               'paste'}
    if action not in allowed:
        return _json({'ok': False,
                      'error': f'action 只能是 {sorted(allowed)}'})
    payload = {'action': action, 'path': str(args.get('path') or ''),
               'name': str(args.get('name') or '')}
    if args.get('template'):
        payload['template'] = str(args.get('template'))
    desk._on_explorer_op(payload)
    # ★ 新建类操作回读校验（假成功最坑 ✓）
    target = ''
    if action in ('new_file', 'new_folder') and payload['path']:
        base = payload['path'] if os.path.isdir(payload['path']) else             os.path.dirname(payload['path'])
        if payload['name']:
            target = os.path.join(base, payload['name'])
        if target and not os.path.exists(target):
            return _json({'ok': False,
                          'error': f'没建出来：{target}（看运行日志）'})
        if action == 'new_folder' and target and not os.path.isdir(target):
            return _json({'ok': False, 'error': '没建成文件夹'})
    return _json({'ok': True, 'action': action,
                  'path': payload['path'], 'name': payload['name'],
                  'created': target})


def _call_strategy_manage(desk, args: Dict[str, Any]) -> str:
    """策略管理里的行 + 两个运行开关（只读 ✓）"""
    from . import user_prefs as _prefs
    settings = _prefs.settings()
    rows = []
    for row in (desk._strategy_manage_rows() or [])[:40]:
        rows.append({key: row.get(key) for key in
                     ('symbol', 'cell', 'name', 'path', 'live', 'file')})
    return _json({'ok': True,
                  'next_on_new_bar': bool(
                      settings.get('strategy_next_on_new_bar', True)),
                  'run_next': bool(settings.get('strategy_run_next', True)),
                  'count': len(rows), 'rows': rows})


def _call_strategy_switch(desk, args: Dict[str, Any]) -> str:
    """开 / 关「新K线 next」和「next 运行」两个开关 ✓"""
    from . import user_prefs as _prefs
    changed = {}
    if args.get('next_on_new_bar') is not None:
        value = bool(args.get('next_on_new_bar'))
        _prefs.set_setting('strategy_next_on_new_bar', value)
        changed['next_on_new_bar'] = value
    if args.get('run_next') is not None:
        value = bool(args.get('run_next'))
        _prefs.set_setting('strategy_run_next', value)
        changed['run_next'] = value
    if not changed:
        return _json({'ok': False,
                      'error': '至少给一个：next_on_new_bar / run_next'})
    desk._on_strategy_manage({})
    settings = _prefs.settings()
    return _json({'ok': True, 'changed': changed,
                  'next_on_new_bar': bool(
                      settings.get('strategy_next_on_new_bar', True)),
                  'run_next': bool(settings.get('strategy_run_next', True))})


def _call_strategy_remove(desk, args: Dict[str, Any]) -> str:
    """删掉图上的策略（指标保留）"""
    symbol = str(args.get('symbol') or '') or _current_symbol(desk)
    if not symbol:
        return _json({'ok': False, 'error': '需要 symbol'})
    desk._on_remove_strategy({'symbol': symbol})
    return _json({'ok': True, 'removed': symbol})


def _call_repl_eval(desk, args: Dict[str, Any]) -> str:
    """在 desk 的 REPL 里跑一段 Python（同步等结果 ✓，最长 30 秒）"""
    code = str(args.get('code') or '').strip()
    if not code:
        return _json({'ok': False, 'error': '需要 code'})
    from .repl import ReplSession
    session = getattr(desk, '_repl_session', None)
    if session is None:
        session = desk._repl_session = ReplSession(
            getattr(desk, 'explorer_root', lambda: '.')() or '.')
    result = session.run(code, timeout=float(args.get('timeout') or 30))
    return _json({'ok': bool(result.get('ok')),
                  'output': str(result.get('output') or '')[:8000]})


def _call_terminal_run(desk, args: Dict[str, Any]) -> str:
    """在 desk 底部终端里执行一条命令（输出在终端面板 ✓）"""
    command = str(args.get('command') or '').strip()
    if not command:
        return _json({'ok': False, 'error': '需要 command'})
    desk._on_terminal_open({'cwd': str(args.get('cwd') or '')
                            or getattr(desk, 'explorer_root', lambda: '')()
                            or '.'})
    desk._on_terminal_input({'text': command})
    return _json({'ok': True, 'command': command,
                  'message': '已发送到终端（输出在「终端」面板 ✓）'})


# ---------------------------------------------------------------- C 批（布局 / 指标库 / 回放 / 截图）
def _call_layout_save(desk, args: Dict[str, Any]) -> str:
    """保存当前布局（实时图表按 tabs 存；本地图表用 `page` 重建 cells ✓）"""
    name = str(args.get('name') or '').strip()
    local = bool(args.get('local'))
    payload: Dict[str, Any] = {'name': name, 'local': local}
    if local:
        page = _active_page(desk, args)
        cells = (getattr(desk, '_local_pages', {}) or {}).get(page) or {}
        if not cells:
            return _json({'ok': False,
                          'error': '当前没有打开的本地图表页（先加载数据集）'})
        rows = []
        for index, symbol in sorted(cells.items()):
            rows.append({
                'symbol': str(symbol),
                'indicators': desk._local_items(str(symbol), int(index),
                                                page),
            })
        payload['cells'] = rows
        payload['page'] = page
    else:
        payload['symbol'] = str(args.get('symbol') or '') \
            or _current_symbol(desk)
    desk._on_layout_save(payload)
    return _json({'ok': True, 'saved': name or '(自动命名)',
                  'local': local})


def _call_layout_delete(desk, args: Dict[str, Any]) -> str:
    key = str(args.get('key') or '').strip()
    if not key:
        return _json({'ok': False, 'error': '需要 key（先用 desk_layouts 看）'})
    desk._on_layout_delete({'key': key, 'local': bool(args.get('local'))})
    return _json({'ok': True, 'deleted': key})


def _call_layout_favorite(desk, args: Dict[str, Any]) -> str:
    key = str(args.get('key') or '').strip()
    if not key:
        return _json({'ok': False, 'error': '需要 key'})
    on = args.get('on') is not False
    desk._on_layout_favorite({'key': key, 'on': on,
                              'local': bool(args.get('local'))})
    return _json({'ok': True, 'key': key, 'favorite': on})


def _call_tv_list(desk, args: Dict[str, Any]) -> str:
    """「指标和策略」页的卡片列表（关键词 / 收藏 / 分页 ✓）"""
    from . import tv_page as _tv
    payload = {'query': str(args.get('query') or ''),
               'tab': str(args.get('tab') or ''),
               'page': int(args.get('page') or 1),
               'size': int(args.get('size') or 12)}
    if args.get('group'):
        payload['group'] = str(args.get('group'))
    data = _tv.list_payload(payload)
    items = []
    for row in (data.get('items') or [])[:24]:
        items.append({key: row.get(key) for key in
                      ('key', 'name', 'title', 'group', 'star', 'kind')})
    return _json({'ok': bool(data.get('ok', True)),
                  'total': data.get('total') or len(items),
                  'items': items})


def _call_tv_detail(desk, args: Dict[str, Any]) -> str:
    key = str(args.get('key') or args.get('id') or '').strip()
    if not key:
        return _json({'ok': False, 'error': '需要 key（来自 desk_tv_list）'})
    from . import tv_page as _tv
    data = _tv.detail_payload({'key': key, 'id': key,
                               'theme': str(args.get('theme') or '')})
    if not data.get('ok'):
        return _json({'ok': False, 'error': data.get('reason') or '没找到'})
    return _json({'ok': True, 'key': key,
                  'title': data.get('title') or data.get('name'),
                  'summary': str(data.get('summary') or '')[:1200],
                  'params': data.get('params') or [],
                  'star': bool(data.get('star'))})


def _call_tv_source(desk, args: Dict[str, Any]) -> str:
    """取指标源码（和编辑器里那份一致 ✓）"""
    key = str(args.get('key') or '').strip()
    if not key:
        return _json({'ok': False, 'error': '需要 key'})
    # 「我的策略」是真实文件（`file:...`）→ 直接读它 ✓
    if key.startswith('file:'):
        path = key[len('file:'):]
        if not os.path.isfile(path):
            return _json({'ok': False, 'error': f'文件不存在：{path}'})
        try:
            text = read_text_smart(path)
        except OSError as error:
            return _json({'ok': False, 'error': f'读不到：{error}'})
        return _json({'ok': True, 'key': key, 'path': path,
                      'text': text[:12000]})
    from . import tv_page as _tv
    data = _tv.script_payload({'key': key})
    if not data.get('ok'):
        return _json({'ok': False, 'error': data.get('reason') or '取不到源码'})
    text = str(data.get('text') or data.get('code') or '')
    return _json({'ok': True, 'key': key, 'path': data.get('path') or '',
                  'text': text[:12000]})


def _call_tv_star(desk, args: Dict[str, Any]) -> str:
    key = str(args.get('key') or '').strip()
    if not key:
        return _json({'ok': False, 'error': '需要 key'})
    from . import tv_page as _tv
    data = _tv.star_payload({'key': key, 'on': args.get('on') is not False})
    return _json({'ok': bool(data.get('ok', True)), 'key': key,
                  'star': bool(data.get('star'))})


def _call_tv_live(desk, args: Dict[str, Any]) -> str:
    """「指标和策略」页：在线取这个合约的 K 线替换本页数据 ✓"""
    page = str(args.get('page') or '')
    symbol = str(args.get('symbol') or '') or _current_symbol(desk)
    if not symbol:
        return _json({'ok': False, 'error': '需要 symbol'})
    desk._on_tv_live({'page': page, 'symbol': symbol,
                      'cycle': int(args.get('cycle') or 60)})
    return _json({'ok': True, 'page': page, 'symbol': symbol})


def _call_tv_script(desk, args: Dict[str, Any]) -> str:
    """把指标源码落成 .py 并在编辑器里打开（已有文件不覆盖 ✓）"""
    key = str(args.get('key') or '').strip()
    if not key:
        return _json({'ok': False, 'error': '需要 key'})
    desk._on_tv_script({'key': key, 'theme': str(args.get('theme') or '')})
    return _json({'ok': True, 'key': key,
                  'message': '已在编辑器里打开（个人指标目录）'})


def _call_tv_reload(desk, args: Dict[str, Any]) -> str:
    """重载「指标和策略」页的卡片（后台线程；结果看页面 ✓）"""
    desk._on_tv_reload({'page': str(args.get('page') or ''),
                        'theme': str(args.get('theme') or '')})
    return _json({'ok': True,
                  'message': '已在后台重载卡片（十几秒，看页面进度 ✓）'})


def _call_replay_trade(desk, args: Dict[str, Any]) -> str:
    """回放中的本地模拟交易（价格按当前回放价位 ✓）"""
    action = str(args.get('action') or 'order').lower()
    symbol = str(args.get('symbol') or '') or _current_symbol(desk)
    if not symbol:
        return _json({'ok': False, 'error': '需要 symbol'})
    if action in ('close', 'reverse', 'all'):
        desk._on_replay_action({'symbol': symbol, 'action': action})
        return _json({'ok': True, 'action': action, 'symbol': symbol})
    side = str(args.get('side') or '').lower()
    volume = int(args.get('volume') or 0)
    price = float(args.get('price') or 0)
    errors = []
    if side not in ('buy', 'sell'):
        errors.append('side 只能是 buy / sell')
    if volume <= 0:
        errors.append('volume 必须是正整数')
    if price < 0:
        errors.append('price 不能为负')
    if errors:
        return _json({'ok': False, 'error': '；'.join(errors)})
    desk._on_replay_order({'symbol': symbol, 'side': side, 'qty': volume,
                           'volume': volume,
                           'price': price or None,
                           'offset': str(args.get('offset') or 'open')})
    return _json({'ok': True, 'symbol': symbol, 'side': side,
                  'volume': volume, 'price': price or '当前价'})


#: 步骤结果的「下一步可做什么」（写进 sequence 的 hint，省一轮 ✓）
STEP_HINTS = {
    'desk_find_indicator': '拿到 resolved 后下一步：desk_add_indicator'
                           '{key:"$0.resolved", local:true}',
    'desk_add_indicator': '想回放：desk_replay{local:true}；'
                          '想删：desk_remove_indicator{key}',
    'desk_set_layout': '布局好了可以：desk_add_indicator{key, local:true}',
    'desk_local': '加载后可以：desk_add_indicator{key, local:true} / '
                  'desk_replay{local:true}',
    'desk_replay': '回放里下单：desk_replay_trade{action:order, …}',
    'desk_status': '用 hints 里的工具继续',
    'desk_templates': '应用模板：desk_apply_template{key}',
}


def _lookup_result(results: List[Dict[str, Any]], path: str) -> Any:
    """`$0.resolved` / `$1.items.0.key` → 取前面步骤里的值 ✓"""
    parts = [item for item in str(path or '').split('.') if item != '']
    if not parts:
        return ''
    index = int(parts[0])
    if index >= len(results):
        return ''
    value: Any = results[index].get('result') or {}
    for part in parts[1:]:
        if isinstance(value, dict):
            value = value.get(part)
        elif isinstance(value, list):
            try:
                value = value[int(part)]
            except (ValueError, IndexError):
                return ''
        else:
            return ''
        if value is None:
            return ''
    return value


def _resolve_refs(value: Any, results: List[Dict[str, Any]]) -> Any:
    """把 args 里的 `$n.path` 占位符换成前面步骤的结果 ✓

    支持两种写法：整串就是占位符（保留原类型），或嵌在字符串里（拼字符串）。
    """
    if isinstance(value, dict):
        return {key: _resolve_refs(item, results)
                for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_refs(item, results) for item in value]
    if not isinstance(value, str):
        return value
    text = value.strip()
    if text.startswith('$') and ' ' not in text:
        resolved = _lookup_result(results, text[1:])
        if resolved != '':
            return resolved
        return value
    # 字符串里嵌占位符：`$0.resolved_extra` 这种整段替换
    import re as _re
    for match in _re.finditer(r'\$(\d+(?:\.\w+)*)', value):
        resolved = _lookup_result(results, match.group(1))
        if resolved != '':
            value = value.replace(match.group(0), str(resolved))
    return value


def _call_sequence(desk, args: Dict[str, Any]) -> str:
    """一次调用执行多步（合并模型轮数 ✓；危险工具必须逐步确认）"""
    steps = args.get('steps')
    if not isinstance(steps, list) or not steps:
        return _json({'ok': False, 'error': '需要 steps 数组（≤6 步）'})
    if len(steps) > 6:
        return _json({'ok': False, 'error': '最多 6 步（太多就分开调）'})
    results: List[Dict[str, Any]] = []
    ok_all = True
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            results.append({'step': index, 'ok': False,
                            'error': 'step 必须是对象'})
            ok_all = False
            break
        name = str(step.get('tool') or '')
        raw_args = step.get('args') if isinstance(step.get('args'), dict) else {}
        # ★ 依赖引用：`$0.resolved` 取前面步骤的结果（查 → 加 一步搞定 ✓）
        step_args = _resolve_refs(raw_args, results)
        if name == 'desk_sequence' or name not in NAMES:
            results.append({'step': index, 'tool': name, 'ok': False,
                            'error': f'不支持的 tool：{name or "(空)"}'})
            ok_all = False
            break
        if name in DANGEROUS:
            results.append({'step': index, 'tool': name, 'ok': False,
                            'error': '危险工具不能放进 sequence（请单独调用并让用户确认）'})
            ok_all = False
            break
        text = call(name, step_args, desk)
        try:
            data = json.loads(text)
        except ValueError:
            data = {'ok': True, 'text': text[:800]}
        row = {'step': index, 'tool': name,
               'ok': bool(data.get('ok', True)),
               'result': data}
        hint = STEP_HINTS.get(name)
        if hint:
            row['hint'] = hint
        results.append(row)
        if not row['ok']:
            ok_all = False
            # ★ 依赖链断开（比如 key 需要先选）→ 停下来，把候选直接回给模型 ✓
            break
    return _json({'ok': ok_all, 'steps': len(results), 'results': results,
                  'next_hint': '全部成功可直接向用户汇报；失败看 results 里的 '
                               'error / candidates'})


# ---------------------------------------------------------------- 图表缩放 / 行情数据
def _chart_page_of(desk, args: Dict[str, Any], local: bool = False) -> str:
    """算「要对哪一页动手」：显式 page > 本地图表的活动页 > 实时图表页 ✓"""
    page = str(args.get('page') or '')
    if page:
        return page
    if local:
        page = str(getattr(desk, '_active_local_page', '') or '')
        if page:
            return page
    symbol = str(args.get('symbol') or '') or _current_symbol(desk)
    return f'chart:{symbol}' if symbol else ''


def _call_draw_toolbox(desk, args: Dict[str, Any]) -> str:
    """右键「画线」：左侧画线工具箱开 / 关（`ui_action{action:"draw_toolbox"}`）"""
    import threading as _threading

    page = _chart_page_of(desk, args, bool(args.get('local')))
    if not page:
        return _json({'ok': False,
                      'error': '没有可操作的图表（先打开一个图表）'})
    event = _threading.Event()
    record: Dict[str, Any] = {'event': event, 'ack': {}}
    try:
        desk._draw_pending = record
        payload: Dict[str, Any] = {'type': 'ui_action',
                                   'action': 'draw_toolbox', 'page': page}
        if args.get('on') is not None:
            payload['on'] = bool(args.get('on'))
        desk.push(payload)
        if not event.wait(BARS_TIMEOUT):
            return _json({'ok': False, 'page': page,
                          'error': '前端没有回执（图表页开着吗？）'})
        ack = dict(record.get('ack') or {})
        if ack.get('ok') is False:
            return _json({'ok': False, 'page': page,
                          'error': ack.get('error') or '前端执行失败'})
        return _json({'ok': True, 'page': page,
                      'toolbox_open': bool(ack.get('on')),
                      'detail': '画线工具箱已打开' if ack.get('on')
                      else '画线工具箱已收起'})
    finally:
        desk._draw_pending = None


def _call_bars(desk, args: Dict[str, Any]) -> str:
    """右键菜单「全部K线 / 最新K线（N 根）」（用户 2026-11-08 ✓）

    以前模型只能去改设置里的 `chart_data_length`（那是**加载长度**），
    右键这两个是**视图缩放** → 现在直连：`ui_action{action:"bars"}` →
    前端 `fitAllBars()` / `showLastBars(count)` → 回执 `bars`（带总根数）。
    """
    import threading as _threading

    raw = str(args.get('action') or 'last').lower()
    mode = ('all' if raw in ('all', 'fit', 'fitall', '全部', '全部k线')
            else 'last')
    count = int(args.get('count') or 300)
    count = max(30, min(count, 5000))
    cell = args.get('cell')
    cell = -1 if cell is None or str(cell) == '' else max(0, int(cell))
    local = bool(args.get('local'))
    page = _chart_page_of(desk, args, local)
    if not page:
        return _json({'ok': False,
                      'error': '没有可操作的图表（先打开一个图表）'})
    pending = getattr(desk, '_bars_pending', None)
    if pending is not None:
        return _json({'ok': False, 'error': '上一个缩放动作还没回来，稍等'})
    event = _threading.Event()
    record: Dict[str, Any] = {'event': event, 'ack': {}}
    try:
        desk._bars_pending = record
        desk.push({'type': 'ui_action', 'action': 'bars', 'mode': mode,
                   'count': count, 'page': page, 'cell': cell,
                   'local': local})
        if not event.wait(BARS_TIMEOUT):
            return _json({'ok': False, 'page': page, 'mode': mode,
                          'error': '前端没有回执（图表页开着吗？）',
                          'hint': '先 desk_status 看有哪些图表页'})
        ack = dict(record.get('ack') or {})
        if ack.get('ok') is False:
            return _json({'ok': False, 'page': page,
                          'error': ack.get('error') or '前端执行失败'})
        return _json({'ok': True, 'page': page, 'mode': mode,
                      'count': 0 if mode == 'all' else count,
                      'cell': ack.get('cell', cell),
                      'bars_loaded': ack.get('bars'),
                      'detail': '全部K线（一次看全）' if mode == 'all'
                      else f'最新 {count} 根'})
    finally:
        desk._bars_pending = None


def _feed_for(desk, symbol: str):
    """找合约对应的行情源（tabs → _feed_for → pick_feed ✓）"""
    info = (getattr(desk, 'tabs', {}) or {}).get(symbol) or {}
    feed = info.get('feed')
    if feed is not None:
        return feed
    picker = getattr(desk, '_feed_for', None)
    if callable(picker):
        try:
            feed = picker(symbol)
        except Exception:                                     # noqa: BLE001
            feed = None
        if feed is not None:
            return feed
    try:
        from .app import pick_feed as _pick
        feeds = getattr(desk, 'feeds', None) or []
        if feeds:
            return _pick(feeds, symbol)
    except Exception:                                         # noqa: BLE001
        pass
    return None


def _cycle_of(desk, args: Dict[str, Any], symbol: str) -> int:
    raw = args.get('cycle')
    if raw not in (None, '', 0):
        resolver = getattr(desk, 'normalize_cycle', None)
        try:
            value = int(resolver(raw) or 0) if callable(resolver) else 0
        except Exception:                                     # noqa: BLE001
            value = 0
        if value > 0:
            return value
        try:
            return int(raw)
        except (TypeError, ValueError):
            pass
    info = (getattr(desk, 'tabs', {}) or {}).get(symbol) or {}
    try:
        return int(info.get('cycle') or 60)
    except (TypeError, ValueError):
        return 60


# ---------------------------------------------------------------- 行情分析（P0/P1/P2）
def _num_at(series, index: int, default: float = 0.0) -> float:
    try:
        value = float(series[index])
        if value != value:                                    # NaN
            return default
        return value
    except Exception:                                         # noqa: BLE001
        return default


def _pivot_levels(frame, limit: int = 80) -> Dict[str, Any]:
    """前高 / 前低（5 根局部极值）+ 斐波那契 + 成交量分布（POC / VAH / VAL）✓"""
    tail = frame.tail(max(20, limit))
    highs = [float(item) for item in tail['high'].tolist()]
    lows = [float(item) for item in tail['low'].tolist()]
    closes = [float(item) for item in tail['close'].tolist()]
    stamp = [_stamp_text(item) for item in tail['datetime'].tolist()]
    volumes = []
    try:
        volumes = [float(item) for item in tail['volume'].tolist()]
    except Exception:                                         # noqa: BLE001
        volumes = [1.0] * len(closes)
    pivots_high: List[Dict[str, Any]] = []
    pivots_low: List[Dict[str, Any]] = []
    for index in range(2, len(closes) - 2):
        window = highs[index - 2:index + 3]
        if highs[index] >= max(window) and highs[index] > highs[index - 1]:
            pivots_high.append({'time': stamp[index],
                                'price': round(highs[index], 4)})
        window_low = lows[index - 2:index + 3]
        if lows[index] <= min(window_low) and lows[index] < lows[index - 1]:
            pivots_low.append({'time': stamp[index],
                               'price': round(lows[index], 4)})
    last = closes[-1] if closes else 0.0
    above = sorted({item['price'] for item in pivots_high if item['price'] > last})
    below = sorted({item['price'] for item in pivots_low if item['price'] < last},
                   reverse=True)
    swing_low = min(lows) if lows else 0.0
    swing_high = max(highs) if highs else 0.0
    fib = {}
    if swing_high > swing_low:
        span = swing_high - swing_low
        for ratio in (0.236, 0.382, 0.5, 0.618, 0.786):
            fib[str(ratio)] = round(swing_high - span * ratio, 4)
    # 成交量分布：按收盘价分 24 桶，找 POC 与 70% 价值区 ✓
    poc = vah = val = None
    if closes and sum(volumes) > 0:
        low_edge, high_edge = min(closes), max(closes)
        if high_edge > low_edge:
            bins = 24
            step = (high_edge - low_edge) / bins
            weights = [0.0] * bins
            for close, volume in zip(closes, volumes):
                index = min(bins - 1, max(0, int((close - low_edge) / step)))
                weights[index] += volume
            top = max(range(bins), key=lambda item: weights[item])
            poc = round(low_edge + (top + 0.5) * step, 4)
            total = sum(weights)
            keep = total * 0.7
            left = right = top
            acc = weights[top]
            while acc < keep and (left > 0 or right < bins - 1):
                left_w = weights[left - 1] if left > 0 else -1
                right_w = weights[right + 1] if right < bins - 1 else -1
                if right_w >= left_w and right < bins - 1:
                    right += 1
                    acc += weights[right]
                elif left > 0:
                    left -= 1
                    acc += weights[left]
                else:
                    break
            val = round(low_edge + left * step, 4)
            vah = round(low_edge + (right + 1) * step, 4)
    return {
        'last': round(last, 4),
        'swing': {'high': round(swing_high, 4), 'low': round(swing_low, 4)},
        'pivot_highs': pivots_high[-6:],
        'pivot_lows': pivots_low[-6:],
        'fib': fib,
        'volume_profile': {'poc': poc, 'vah': vah, 'val': val},
        'resistance': above[:3],
        'support': below[:3],
        'hint': 'resistance = 上方最近的前高；support = 下方最近的前低；'
                'fib 是从区间高点往下回撤的比例位 ✓',
    }


def _stats_table(frame) -> Dict[str, Any]:
    """ATR / 波动率 / 分位数 / 趋势斜率 / RSI / MA（行情"体检" ✓）"""
    tail = frame.tail(160)
    closes = [float(item) for item in tail['close'].tolist()]
    highs = [float(item) for item in tail['high'].tolist()]
    lows = [float(item) for item in tail['low'].tolist()]
    out: Dict[str, Any] = {'bars': len(closes)}
    if not closes:
        return out
    out['last_close'] = round(closes[-1], 4)
    changes = []
    for index in range(1, len(closes)):
        if closes[index - 1]:
            changes.append(closes[index] / closes[index - 1] - 1.0)
    if changes:
        mean = sum(changes) / len(changes)
        variance = sum((item - mean) ** 2 for item in changes) / len(changes)
        out['volatility_pct'] = round((variance ** 0.5) * 100, 4)
        out['change_std_pct'] = out['volatility_pct']
    ranges = [highs[index] - lows[index] for index in range(len(closes))]
    atr_window = ranges[-14:] if len(ranges) >= 14 else ranges
    if atr_window:
        out['atr14'] = round(sum(atr_window) / len(atr_window), 4)
        out['atr_pct'] = round(out['atr14'] / closes[-1] * 100, 4) \
            if closes[-1] else 0.0
    for name, ratio in (('p05', 0.05), ('p25', 0.25), ('p50', 0.5),
                        ('p75', 0.75), ('p95', 0.95)):
        ordered = sorted(closes)
        index = min(len(ordered) - 1, max(0, int(round(ratio * (len(ordered) - 1)))))
        out[name] = round(ordered[index], 4)
    for window in (5, 20, 60):
        if len(closes) >= window:
            out[f'ma{window}'] = round(
                sum(closes[-window:]) / window, 4)
    # 趋势：最近 30 根收盘的线性回归斜率（每根均价变化 / 波动）
    window = closes[-30:] if len(closes) >= 30 else closes
    if len(window) >= 5:
        count = len(window)
        mean_x = (count - 1) / 2.0
        mean_y = sum(window) / count
        numerator = sum((index - mean_x) * (value - mean_y)
                        for index, value in enumerate(window))
        denominator = sum((index - mean_x) ** 2 for index in range(count))
        slope = numerator / denominator if denominator else 0.0
        out['slope_per_bar'] = round(slope, 6)
        out['trend'] = ('上涨' if slope > 0.0001 * abs(mean_y) else
                        ('下跌' if slope < -0.0001 * abs(mean_y) else '震荡'))
    # RSI(14)
    if len(closes) > 15:
        gains = losses = 0.0
        for index in range(len(closes) - 14, len(closes)):
            delta = closes[index] - closes[index - 1]
            if delta >= 0:
                gains += delta
            else:
                losses -= delta
        avg_gain = gains / 14
        avg_loss = losses / 14
        rsi = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
        out['rsi14'] = round(rsi, 2)
    volumes = []
    try:
        volumes = [float(item) for item in tail['volume'].tolist()]
    except Exception:                                         # noqa: BLE001
        volumes = []
    if len(volumes) >= 20:
        recent = sum(volumes[-5:]) / 5
        base = sum(volumes[-20:]) / 20
        out['volume_ratio'] = round(recent / base, 3) if base else 0.0
    out['hint'] = ('atr_pct 越大波动越大；trend 看斜率；rsi14 > 70 超买、'
                   '< 30 超卖；volume_ratio > 1.5 放量 ✓')
    return out


def _pattern_rows(frame, limit: int = 10) -> List[Dict[str, Any]]:
    """K 线形态（吞没 / 锤子 / 射击之星 / 十字星 / 三兵三鸦 / 缺口 / 内包 ✓）"""
    tail = frame.tail(min(80, max(20, limit * 8)))
    rows = []
    data = []
    for _, row in tail.iterrows():
        data.append({'time': _stamp_text(row.get('datetime')),
                     'open': float(row.get('open') or 0),
                     'high': float(row.get('high') or 0),
                     'low': float(row.get('low') or 0),
                     'close': float(row.get('close') or 0)})
    for index in range(1, len(data)):
        bar = data[index]
        prev = data[index - 1]
        body = abs(bar['close'] - bar['open'])
        full = max(1e-9, bar['high'] - bar['low'])
        upper = bar['high'] - max(bar['close'], bar['open'])
        lower = min(bar['close'], bar['open']) - bar['low']
        found = []
        if (bar['close'] > bar['open'] and prev['close'] < prev['open']
                and bar['close'] >= prev['open']
                and bar['open'] <= prev['close'] and body > 0):
            found.append(('看涨吞没', 'bull'))
        if (bar['close'] < bar['open'] and prev['close'] > prev['open']
                and bar['close'] <= prev['open']
                and bar['open'] >= prev['close'] and body > 0):
            found.append(('看跌吞没', 'bear'))
        if body <= full * 0.1:
            found.append(('十字星', 'neutral'))
        if lower >= body * 2 and upper <= body and body > 0:
            found.append(('锤子线', 'bull'))
        if upper >= body * 2 and lower <= body and body > 0:
            found.append(('射击之星', 'bear'))
        if (bar['close'] > bar['open'] and body >= full * 0.85):
            found.append(('大阳线', 'bull'))
        if (bar['close'] < bar['open'] and body >= full * 0.85):
            found.append(('大阴线', 'bear'))
        if bar['low'] > prev['high']:
            found.append(('向上跳空', 'bull'))
        if bar['high'] < prev['low']:
            found.append(('向下跳空', 'bear'))
        if bar['high'] <= prev['high'] and bar['low'] >= prev['low']:
            found.append(('内包线', 'neutral'))
        for name, tone in found:
            rows.append({'time': bar['time'], 'pattern': name,
                         'tone': tone,
                         'close': round(bar['close'], 4)})
    # 三兵 / 三鸦
    for index in range(2, len(data)):
        three = data[index - 2:index + 1]
        if all(item['close'] > item['open'] for item in three) \
                and three[0]['close'] < three[1]['close'] < three[2]['close']:
            rows.append({'time': three[-1]['time'], 'pattern': '红三兵',
                         'tone': 'bull', 'close': round(three[-1]['close'], 4)})
        if all(item['close'] < item['open'] for item in three) \
                and three[0]['close'] > three[1]['close'] > three[2]['close']:
            rows.append({'time': three[-1]['time'], 'pattern': '三只乌鸦',
                         'tone': 'bear', 'close': round(three[-1]['close'], 4)})
    # ★ 同一形态 3 根内只留最后一次（连续红三兵会重复 4 次 ✗）
    deduped: List[Dict[str, Any]] = []
    seen_at: Dict[str, int] = {}
    order = {row['time']: index for index, row in enumerate(data)}
    for row in rows:
        index = order.get(row['time'], 0)
        last = seen_at.get(row['pattern'])
        if last is not None and index - last < 3:
            if deduped and deduped[-1]['pattern'] == row['pattern']:
                deduped[-1] = row
            seen_at[row['pattern']] = index      # 替换也要推进，否则漏合并 ✓
            continue
        seen_at[row['pattern']] = index
        deduped.append(row)
    return deduped[-max(1, limit):]


def _depth_table(desk, symbol: str, limit: int = 5) -> Dict[str, Any]:
    """五档买卖压力（复用后端 `book_payload`，不再单独订阅 ✓）"""
    builder = getattr(desk, 'book_payload', None)
    if not callable(builder):
        return {'ok': False, 'error': '后端没有二级报价（版本较旧）'}
    try:
        payload = builder(symbol) or {}
    except Exception as error:                                # noqa: BLE001
        return {'ok': False,
                'error': f'取 {symbol} 盘口失败：{type(error).__name__}: {error}'}
    bids = list(payload.get('bids') or [])[:max(1, limit)]
    asks = list(payload.get('asks') or [])[:max(1, limit)]

    def volume(item) -> float:
        try:
            return float(item.get('volume') or 0)
        except Exception:                                     # noqa: BLE001
            return 0.0

    bid_volume = sum(volume(item) for item in bids)
    ask_volume = sum(volume(item) for item in asks)
    total = bid_volume + ask_volume
    ratio = (bid_volume / ask_volume) if ask_volume else 0.0
    last = payload.get('last_price')
    best_bid = bids[0].get('price') if bids else None
    best_ask = asks[0].get('price') if asks else None
    spread = None
    try:
        if best_bid is not None and best_ask is not None:
            spread = round(float(best_ask) - float(best_bid), 4)
    except Exception:                                         # noqa: BLE001
        spread = None
    return {
        'ok': True, 'symbol': symbol, 'last_price': last,
        'best_bid': best_bid, 'best_ask': best_ask, 'spread': spread,
        'bids': bids, 'asks': asks,
        'bid_volume': round(bid_volume, 2),
        'ask_volume': round(ask_volume, 2),
        'bid_ratio': round(ratio, 3),
        'imbalance': round((bid_volume - ask_volume) / total, 3) if total else 0.0,
        'pressure': ('买盘偏强' if ratio > 1.2 else
                     ('卖盘偏强' if 0 < ratio < 0.8 else '均衡')),
        'hint': 'bid_ratio > 1.2 买盘厚；< 0.8 卖盘厚；imbalance 是归一化差 ✓',
    }


def _market_digest(frame, meta: Dict[str, Any]) -> Dict[str, Any]:
    """把 K 线压成一段**紧凑文本**（省 token，长对话不炸上下文 ✓）"""
    table = _kline_rows(frame, 60)
    stats = _stats_table(frame)
    levels = _pivot_levels(frame)
    rows = table['rows'][-5:]
    lines = [f"{meta.get('symbol') or meta.get('name') or '?'}"
             f" 周期 {meta.get('cycle') or '-'}s"
             f" 最新 {stats.get('last_close')}"
             f" 涨跌 {table['stats'].get('change_pct')}%"
             f" 高/低 {table['stats'].get('high')}/{table['stats'].get('low')}"]
    if stats.get('ma5') and stats.get('ma20'):
        lines.append(f"MA5 {stats['ma5']} / MA20 {stats['ma20']}"
                     f" 趋势 {stats.get('trend')}"
                     f" RSI {stats.get('rsi14')}"
                     f" ATR% {stats.get('atr_pct')}")
    if levels.get('support') or levels.get('resistance'):
        lines.append(f"支撑 {levels.get('support')} 阻力 {levels.get('resistance')}")
    lines.append('最近 5 根（时间 O/H/L/C）:')
    for row in rows:
        lines.append(f"  {row[0]} {row[1]}/{row[2]}/{row[3]}/{row[4]}")
    return {'ok': True, 'text': '\n'.join(lines), 'stats': stats,
            'levels': levels}


def _scan_one(desk, symbol: str, args: Dict[str, Any]):
    """扫一个合约：算指标 → 取最后两个值 → 判断条件 ✓"""
    limit = max(2, min(int(args.get('limit') or 120), 500))
    frame, meta = _market_frame(desk, {
        'symbol': symbol,
        'cycle': args.get('cycle'),
        'limit': limit + 200,
        # ★ 本地 CSV 扫描：local + name 透传（否则永远「没有行情源」✗）
        'local': bool(args.get('local')),
        'name': args.get('name') or '',
    })
    if frame is None:
        return {'symbol': symbol, 'ok': False, 'error': meta.get('error', '')}
    data = _indicator_tables(desk, {
        'key': args.get('key') or '', 'keys': args.get('keys') or [],
        'params': args.get('params') or {}, 'limit': 3,
    }, frame, meta)
    if not data.get('ok'):
        return {'symbol': symbol, 'ok': False,
                'error': data.get('error') or '指标算不出来',
                'candidates': data.get('candidates') or []}
    values = []
    for item in data.get('items') or []:
        points = item.get('points') or []
        values.append({'key': item.get('key'), 'label': item.get('label'),
                       'last': points[-1][1] if points else None,
                       'prev': points[-2][1] if len(points) > 1 else None})
    return {'symbol': symbol, 'ok': True, 'values': values,
            'last_close': frame['close'].tolist()[-1] if len(frame) else None}


def _scan_match(values: List[Dict[str, Any]], op: str,
                target: Optional[float]) -> Optional[bool]:
    """条件判断：gt / lt / cross_up / cross_down / above / below ✓"""
    if not values:
        return None
    item = values[0]
    last, prev = item.get('last'), item.get('prev')
    if last is None:
        return None
    if op in ('cross_up', '上穿'):
        return (prev is not None and target is not None
                and prev <= target < last)
    if op in ('cross_down', '下穿'):
        return (prev is not None and target is not None
                and prev >= target > last)
    if op in ('gt', '>', 'above', '大于'):
        return target is not None and last > target
    if op in ('lt', '<', 'below', '小于'):
        return target is not None and last < target
    return None


def _call_scan(desk, args: Dict[str, Any]) -> str:
    """多合约批量筛（「哪些合约 MACD 金叉 / RSI < 30」✓）"""
    raw = args.get('symbols')
    symbols: List[str] = []
    if isinstance(raw, (list, tuple)):
        symbols = [str(item) for item in raw if str(item or '').strip()]
    if not symbols:
        symbol = str(args.get('symbol') or '') or _current_symbol(desk)
        if symbol:
            symbols = [symbol]
    if not symbols:
        return _json({'ok': False,
                      'error': '给 symbols（合约列表），或用当前图表合约'})
    symbols = symbols[:30]
    if not (args.get('key') or args.get('keys')):
        return _json({'ok': False, 'error': '给指标 key（先 desk_find_indicator）'})
    op = str(args.get('op') or 'gt').lower()
    target = args.get('value')
    target = None if target in (None, '') else float(target)
    if op in ('cross_up', 'cross_down', 'gt', 'lt') and target is None:
        return _json({'ok': False,
                      'error': f'{op} 需要 value（阈值 / 穿越价）'})
    rows = []
    matches = []
    for symbol in symbols:
        try:
            row = _scan_one(desk, symbol, args)
        except Exception as error:                            # noqa: BLE001
            row = {'symbol': symbol, 'ok': False,
                   'error': f'{type(error).__name__}: {error}'}
        row['match'] = _scan_match(row.get('values') or [], op, target) \
            if row.get('ok') else None
        rows.append(row)
        if row.get('match'):
            matches.append(row)
    return _json({
        'ok': True, 'op': op, 'value': target,
        'condition': f"{args.get('key') or args.get('keys')} {op}"
                     f"{'' if target is None else ' ' + str(target)}",
        'scanned': len(rows), 'matched': len(matches),
        'matches': matches[:12], 'rows': rows[:30],
        'hint': 'match=true 就是符合条件的合约；rows 里带每个合约的最新值 ✓',
    })


def _strategy_payloads(desk) -> List[Dict[str, Any]]:
    """取策略实验室的结果（`_extract` 已含 metrics / equity / trades / signals）✓"""
    from . import strategy_lab as _lab
    labs = getattr(desk, '_strategy_labs', {}) or {}
    out = []
    for key, lab in list(labs.items()):
        instances = list(getattr(lab, '_instances', []) or [])
        if not instances:
            continue
        for inst in instances[:1]:
            try:
                data = lab._extract(inst)
            except Exception as error:                        # noqa: BLE001
                out.append({'id': str(key),
                            'file': os.path.basename(str(
                                getattr(lab, 'file', '') or '')),
                            'error': f'{type(error).__name__}: {error}'})
                continue
            out.append({'id': str(key),
                        'file': os.path.basename(str(
                            getattr(lab, 'file', '') or '')),
                        'mode': str(getattr(lab, 'mode', '') or ''),
                        'name': data.get('name'),
                        'metrics': data.get('metrics') or {},
                        'equity': data.get('equity') or [],
                        'pnl': data.get('pnl') or [],
                        'contracts': data.get('contracts') or []})
    return out


def _call_strategy_data(desk, args: Dict[str, Any]) -> str:
    """回测结果 / 策略信号（收益、回撤、逐笔、最新多空信号 ✓）"""
    action = str(args.get('action') or 'summary').lower()
    limit = max(1, min(int(args.get('limit') or 20), 200))
    wanted = str(args.get('id') or '')
    payloads = [row for row in _strategy_payloads(desk)
                if not wanted or row.get('id') == wanted]
    if not payloads:
        return _json({'ok': False,
                      'error': '还没有回测结果（先 desk_backtest_run）',
                      'hint': '跑完回测再用本工具拿 收益 / 回撤 / 逐笔 / 信号'})
    row = payloads[-1]
    if action in ('summary', 'metrics'):
        out = {'ok': True, 'id': row.get('id'), 'file': row.get('file'),
               'mode': row.get('mode'), 'name': row.get('name'),
               'metrics': row.get('metrics')}
        equity = list(row.get('equity') or [])
        out['equity_points'] = len(equity)
        out['equity_tail'] = equity[-min(10, len(equity)):]
        contracts = []
        for contract in row.get('contracts') or []:
            contracts.append({
                'contract': contract.get('contract'),
                'symbol': contract.get('symbol'),
                'bars': len(contract.get('bars') or []),
                'trade_count': contract.get('trade_count'),
            })
        out['contracts'] = contracts
        out['hint'] = ('action=trades 拿逐笔；action=signals 拿最新多空信号；'
                       'action=equity 拿净值曲线 ✓')
        return _json(out)
    if action == 'trades':
        trades = []
        for contract in row.get('contracts') or []:
            for item in contract.get('trades') or []:
                trades.append({'contract': contract.get('symbol'),
                               **item})
        return _json({'ok': True, 'id': row.get('id'), 'count': len(trades),
                      'trades': trades[-limit:],
                      'hint': 'side = 多 / 空；pnl 是该笔盈亏 ✓'})
    if action == 'equity':
        equity = list(row.get('equity') or [])
        return _json({'ok': True, 'id': row.get('id'),
                      'points': len(equity), 'equity': equity[-limit:]})
    if action == 'signals':
        signals = []
        for contract in row.get('contracts') or []:
            for item in contract.get('signals') or []:
                signals.append({'contract': contract.get('symbol'), **item})
        return _json({'ok': True, 'id': row.get('id'),
                      'count': len(signals), 'signals': signals[-limit:],
                      'hint': 'signals 是策略在 K 线上的买 / 卖标记 ✓'})
    return _json({'ok': False,
                  'error': 'action 只能是 summary / trades / equity / signals'})


def _market_frame(desk, args: Dict[str, Any]):
    """取 K 线 DataFrame：本地 CSV 或实时行情源（失败给中文原因 ✓）"""
    limit = max(10, min(int(args.get('limit') or 60), 500))
    if bool(args.get('local')) or args.get('name'):
        name = str(args.get('name') or '') or _local_symbol(desk, args)
        if not name:
            return None, {'error': '没有指定本地数据'
                                   '（先 desk_local{action:"list"}）'}
        store = getattr(desk, 'local_store', None)
        try:
            frame = store().frame(name) if callable(store) else None
        except Exception as error:                            # noqa: BLE001
            return None, {'error': f'读本地数据失败：{error}'}
        if frame is None or not len(frame):
            return None, {'error': f'本地数据 {name} 是空的'}
        return frame, {'source': 'local', 'name': name}
    symbol = str(args.get('symbol') or '') or _current_symbol(desk)
    if not symbol:
        return None, {'error': '没有合约：给个 symbol，或先打开图表'}
    cycle = _cycle_of(desk, args, symbol)
    feed = _feed_for(desk, symbol)
    if feed is None:
        return None, {'error': f'没有 {symbol} 的行情源（离线模式？）',
                      'hint': '本地历史数据用 local:true + name'
                              '（desk_local{action:"list"}）'}
    try:
        # ★ 多取一点做指标预热（MA / MACD 要前置窗口 ✓）
        frame = feed.klines(symbol, cycle, limit + 200)
    except Exception as error:                                # noqa: BLE001
        return None, {'error': f'取 {symbol} K 线失败：{error}'}
    if frame is None or not len(frame):
        return None, {'error': f'{symbol} 没有 K 线'
                               '（行情未就绪 / 周期不支持）',
                      'cycle': cycle}
    return frame, {'source': 'realtime', 'symbol': symbol, 'cycle': cycle}


def _stamp_text(value) -> str:
    """K 线时间戳（纳秒 int64 / Timestamp）→ 可读时间 ✓"""
    try:
        import pandas as pd
        return pd.to_datetime(int(value)).strftime('%Y-%m-%d %H:%M')
    except Exception:                                         # noqa: BLE001
        return str(value)[:19].replace('T', ' ')


def _kline_rows(frame, limit: int) -> Dict[str, Any]:
    """DataFrame → `{columns, rows, first, last, stats}`（模型能直接读 ✓）"""
    columns = ['time', 'open', 'high', 'low', 'close', 'volume']
    tail = frame.tail(limit)
    rows: List[List[Any]] = []
    for _, row in tail.iterrows():
        rows.append([_stamp_text(row.get('datetime')),
                     round(float(row.get('open') or 0), 4),
                     round(float(row.get('high') or 0), 4),
                     round(float(row.get('low') or 0), 4),
                     round(float(row.get('close') or 0), 4),
                     round(float(row.get('volume') or 0), 2)])
    stats: Dict[str, Any] = {}
    try:
        closes = tail['close'].astype('float64')
        highs = tail['high'].astype('float64')
        lows = tail['low'].astype('float64')
        first, last = float(closes.iloc[0]), float(closes.iloc[-1])
        stats = {'first_close': round(first, 4),
                 'last_close': round(last, 4),
                 'change': round(last - first, 4),
                 'change_pct': (round((last / first - 1) * 100, 3)
                                if first else 0.0),
                 'high': round(float(highs.max()), 4),
                 'low': round(float(lows.min()), 4),
                 'bars': int(len(tail))}
        if len(tail) >= 5:
            stats['ma5'] = round(float(closes.rolling(5).mean().iloc[-1]), 4)
        if len(tail) >= 20:
            stats['ma20'] = round(float(closes.rolling(20).mean().iloc[-1]), 4)
    except Exception:                                         # noqa: BLE001
        pass
    return {'columns': columns, 'rows': rows,
            'first': rows[0][0] if rows else '',
            'last': rows[-1][0] if rows else '', 'stats': stats}


def _quote_row(desk, symbol: str) -> Dict[str, Any]:
    """最新报价（优先 tick 缓存，退回表格快照 ✓）"""
    cache = getattr(desk, '_quote_cache', {}) or {}
    row = cache.get(symbol) or (getattr(desk, '_last_rows', {}) or {}).get(
        symbol) or {}
    out: Dict[str, Any] = {'symbol': symbol}
    for key in ('last_price', 'last', 'bid_price', 'ask_price', 'volume',
                'open_interest', 'change', 'change_pct', 'update_time'):
        if row.get(key) not in (None, ''):
            out[key] = row.get(key)
    return out


def _indicator_tables(desk, args: Dict[str, Any], frame,
                      meta: Dict[str, Any]) -> Dict[str, Any]:
    """指标 key → 数值表（`[{label, key, kind, points}]` ✓）"""
    raw: List[str] = []
    if args.get('key'):
        raw.append(str(args.get('key')))
    if isinstance(args.get('keys'), (list, tuple)):
        raw.extend(str(item) for item in args.get('keys') or [])
    keys: List[str] = []
    hints: List[Dict[str, Any]] = []
    for item in raw:
        found = resolve_indicator(item)
        key = str(found.get('key') or '')
        if key:
            if key not in keys:
                keys.append(key)
        else:
            hints.append({'query': item,
                          'candidates': found.get('candidates')})
    if not keys:
        return {'ok': False, 'error': '没有可用的指标 key',
                'candidates': hints,
                'hint': '先用 desk_find_indicator{query:"macd"} 查 key'}
    limit = max(5, min(int(args.get('limit') or 30), 500))
    params = args.get('params') if isinstance(args.get('params'), dict) else {}
    items = [{'key': key, 'params': dict(params)} for key in keys]
    symbol = str(meta.get('symbol') or meta.get('name') or '')
    compute = getattr(desk, '_indicator_payload_for', None)
    if not callable(compute):
        return {'ok': False, 'error': '后端缺少指标计算（版本较旧）'}
    try:
        payload = compute(symbol, items, frame=frame) or {}
    except Exception as error:                                # noqa: BLE001
        return {'ok': False, 'error': f'指标计算失败：{error}'}
    tables = []
    for line in payload.get('items') or []:
        data = list(line.get('data') or [])[-limit:]
        tables.append({
            'key': line.get('key') or line.get('source'),
            'label': line.get('label'),
            'kind': line.get('kind'),
            'pane': line.get('pane') or ('主图' if line.get('overlay')
                                        else '副图'),
            'points': [[_stamp_text(stamp), round(float(value), 6)]
                       for stamp, value in data],
            'latest': round(float(data[-1][1]), 6) if data else None,
        })
    return {'ok': True, 'symbol': symbol, 'items': tables,
            'hint': 'points = [时间, 数值]；金叉 / 背离按两列自己比 ✓'}


def _call_macro(desk, args: Dict[str, Any]) -> str:
    """宏观指标（GDP / CPI / PMI / PPI / M2）✓"""
    try:
        from . import info as _info
    except Exception as error:                                # noqa: BLE001
        return _json({'ok': False, 'error': f'资讯模块不可用：{error}'})
    names = [str(item) for item in (args.get('names') or []) if item]
    limit = max(1, min(int(args.get('limit') or 12), 60))
    if args.get('refresh'):
        import threading as _threading
        event = _threading.Event()
        _info.macro(names or None, limit=limit, refresh=True,
                    on_done=lambda payload: event.set())
        event.wait(12.0)
    data = _info.macro(names or None, limit=limit)
    if data.get('installed') is False:
        return _json({'ok': False, 'need_install': True,
                      'error': '没装 AkShare',
                      'hint': 'pip install "minibt[news]"（或 pip install akshare）'})
    items = []
    for item in data.get('items') or []:
        items.append({'key': item.get('key'), 'name': item.get('name'),
                      'unit': item.get('unit'),
                      'latest': (item.get('latest') or [None, None])[0],
                      'value': (item.get('latest') or [None, None])[1],
                      'points': item.get('points') or []})
    return _json({'ok': True, 'count': len(items), 'items': items,
                  'names': data.get('names'),
                  'stale': data.get('stale'),
                  'hint': 'points = [[期, 值], …] 升序；stale=true 是缓存'})


def _call_fundamentals(desk, args: Dict[str, Any]) -> str:
    """标的资料：合约规则 / 库存 / 基差 / 简介 ✓"""
    try:
        from . import info as _info
    except Exception as error:                                # noqa: BLE001
        return _json({'ok': False, 'error': f'资讯模块不可用：{error}'})
    symbol = str(args.get('symbol') or '')
    if not symbol:
        return _json({'ok': False, 'error': '需要 symbol'
                                          '（如 SHFE.ag2612 / 600519）'})
    data = _info.symbol_info(symbol, desk)
    if data.get('need_install'):
        return _json({'ok': False, 'need_install': True,
                      'error': '没装 AkShare',
                      'hint': 'pip install "minibt[news]"（或 pip install akshare）'})
    action = str(args.get('action') or 'all').lower()
    if action == 'all':
        payload = {'ok': True, 'symbol': symbol,
                   'kind': data.get('kind') or ('futures'
                                                if data.get('variety')
                                                else 'stock'),
                   'variety': data.get('variety'),
                   'futu': data.get('futu'),
                   'profile': data.get('profile'),
                   'contract': data.get('contract'),
                   'inventory': data.get('inventory'),
                   'basis': data.get('basis'),
                   'financials': data.get('financials'),
                   'notices': data.get('notices'),
                   'capital': data.get('capital'),
                   'hint': '期货：contract / inventory / basis；'
                           '股票：profile（富途优先）/ capital / financials / '
                           'notices'}
        if data.get('profile_note'):
            payload['note'] = data['profile_note']
        return _json(payload)
    payload = data.get(action)
    if payload is None:
        return _json({'ok': False,
                      'error': 'action 只能是 all / contract / inventory / '
                               'basis / profile'})
    return _json({'ok': True, 'symbol': symbol, 'action': action,
                  'data': payload})


def _call_ta(desk, args: Dict[str, Any]) -> str:
    """技术分析：options / snapshot / set / reset（信号制 ✓）"""
    from . import ta as _ta
    action = str(args.get('action') or 'options').lower()
    if action in ('options', 'list'):
        data = _ta.options(only_signal=args.get('all') is not True)
        return _json({'ok': True, 'count': data.get('count'),
                      'items': data.get('items'),
                      'groups': data.get('groups'),
                      'template': _ta.template(),
                      'templates': sorted(_ta.templates()),
                      'active': _ta.active_name(),
                      'hint': '带 signal 的指标才能直接用于技术分析；'
                              'all=true 可看全部（可自己配 signal）'})
    if action == 'reset':
        _ta.reset_template()
        return _json({'ok': True, 'reset': True,
                      'template': _ta.template(),
                      'templates': sorted(_ta.templates())})
    if action in ('templates', 'list_templates'):
        return _json({'ok': True, 'templates': sorted(_ta.templates()),
                      'active': _ta.active_name(),
                      'items': _ta.template()})
    if action in ('use', 'activate'):
        data = _ta.activate(str(args.get('name') or ''))
        return _json({**data, 'items': _ta.template()})
    if action in ('save', 'save_template'):
        name = str(args.get('name') or '').strip()
        rows = args.get('rows')
        if not name or not isinstance(rows, list):
            return _json({'ok': False,
                          'error': 'save 需要 name + rows'})
        data = _ta.save_named(name, rows)
        return _json({**data, 'items': _ta.template()})
    if action == 'delete':
        data = _ta.delete_named(str(args.get('name') or ''))
        return _json({**data, 'items': _ta.template()})
    if action == 'set':
        rows = args.get('rows')
        if not isinstance(rows, list):
            return _json({'ok': False,
                          'error': 'set 需要 rows（模板条目数组）'})
        data = _ta.save_template(rows)
        return _json({**data, 'template': _ta.template()})
    if action != 'snapshot':
        return _json({'ok': False,
                      'error': 'action 只能是 options / snapshot / set / reset'})
    symbol = str(args.get('symbol') or '') or _current_symbol(desk)
    getter = getattr(desk, '_ta_frame', None)
    frame = getter(symbol) if callable(getter) else None
    if frame is None:
        return _json({'ok': False, 'symbol': symbol,
                      'error': '没有 K 线数据（先打开图表）'})
    rows = args.get('rows') if isinstance(args.get('rows'), list) else None
    data = _ta.snapshot(frame, rows)
    data.pop('ok', None)
    return _json({'ok': True, 'symbol': symbol, **data,
                  'hint': 'rows 里 signal：1 多 / 0 中立 / -1 空；'
                          '没有自定义模板时是内置默认（RSI / MA 全家）'})


def _call_news(desk, args: Dict[str, Any]) -> str:
    """资讯（快讯 / 要闻 / 个股 / 期货 / 搜索）—— AkShare 可选依赖 ✓"""
    try:
        from . import info as _info
    except Exception as error:                                # noqa: BLE001
        return _json({'ok': False, 'error': f'资讯模块不可用：{error}'})
    action = str(args.get('action') or 'latest').lower()
    limit = max(1, min(int(args.get('limit') or 20), 200))
    if action in ('status', 'health'):
        return _json(_info.status())
    if action in ('search', 'find'):
        query = str(args.get('query') or '')
        if not query:
            return _json({'ok': False, 'error': 'search 需要 query'})
        data = _info.news(query=query, limit=limit)
        return _json({'ok': True, 'query': query, 'count': data['count'],
                      'items': data['items'],
                      'hint': '只搜本地缓存；要新内容加 refresh=true'})
    kind = {'latest': 'flash', 'flash': 'flash', 'quick': 'flash',
            'market': 'market', 'symbol': 'symbol', 'stock': 'symbol',
            'futures': 'futures', 'future': 'futures'}.get(action, 'flash')
    symbol = str(args.get('symbol') or '')
    if kind == 'symbol' and not symbol:
        return _json({'ok': False,
                      'error': '个股新闻需要 symbol（600519 / 000001）'})
    if args.get('refresh'):
        import threading as _threading
        event = _threading.Event()

        def done(payload):
            event.set()

        _info.refresh_news(kind, symbol, limit=limit, on_done=done)
        event.wait(8.0)
    data = _info.news(kind, symbol, limit=limit)
    if data.get('installed') is False:
        return _json({'ok': False, 'need_install': True,
                      'error': '没装 AkShare',
                      'hint': 'pip install "minibt[news]"（或 pip install akshare）'})
    rows = [{'title': item.get('title'), 'summary': item.get('summary'),
             'source': item.get('source'), 'time': item.get('published'),
             'url': item.get('url')} for item in data.get('items') or []]
    return _json({'ok': True, 'kind': kind, 'symbol': symbol,
                  'count': len(rows), 'items': rows,
                  'stale': data.get('stale'),
                  'hint': 'stale=true 说明是缓存；要最新加 refresh=true'})


def _call_calendar(desk, args: Dict[str, Any]) -> str:
    """财经日历（今天 / 未来 N 天 / 指定某天）✓"""
    try:
        from . import info as _info
    except Exception as error:                                # noqa: BLE001
        return _json({'ok': False, 'error': f'资讯模块不可用：{error}'})
    action = str(args.get('action') or 'today').lower()
    days = max(1, min(int(args.get('days') or 3), 7))
    day = str(args.get('day') or '')
    limit = max(1, min(int(args.get('limit') or 40), 500))
    if action == 'today':
        days, day = 1, ''
    elif action == 'day':
        if not day:
            return _json({'ok': False,
                          'error': 'action=day 需要 day=YYYY-MM-DD'})
        days = 1
    if args.get('refresh'):
        import threading as _threading
        event = _threading.Event()
        _info.refresh_calendar(days=max(days, 2),
                               on_done=lambda payload: event.set())
        event.wait(10.0)
    data = _info.calendar(days=days, day=day or None, limit=limit * 3)
    if data.get('installed') is False:
        return _json({'ok': False, 'need_install': True,
                      'error': '没装 AkShare',
                      'hint': 'pip install "minibt[news]"（或 pip install akshare）'})
    rows = [{'day': item.get('day'), 'time': item.get('time'),
             'region': item.get('region'), 'event': item.get('event'),
             'actual': item.get('actual'), 'forecast': item.get('forecast'),
             'previous': item.get('previous'),
             'importance': item.get('importance')}
            for item in data.get('items') or []]
    # 高重要性优先（日历一天上百条，全给会占满上下文 ✓）
    rows.sort(key=lambda row: (-int(row.get('importance') or 0),
                               str(row.get('day') or ''),
                               str(row.get('time') or '')))
    items = rows[:limit]
    return _json({'ok': True, 'days': data.get('days'), 'day': day,
                  'count': len(items), 'items': items,
                  'stale': data.get('stale'),
                  'hint': 'importance 2 = 高（标黄）；stale=true 是缓存'})


def _call_market(desk, args: Dict[str, Any]) -> str:
    """行情数据：summary / quote / klines / indicator（给模型**数字** ✓）"""
    action = str(args.get('action') or 'summary').lower()
    limit = max(10, min(int(args.get('limit') or 60), 500))
    if action == 'quote':
        symbols = [str(item) for item in (args.get('symbols') or []) if item]
        if not symbols:
            symbol = str(args.get('symbol') or '') or _current_symbol(desk)
            symbols = [symbol] if symbol else []
        if not symbols:
            return _json({'ok': False, 'error': '给 symbol 或 symbols'})
        return _json({'ok': True,
                      'quotes': [_quote_row(desk, item)
                                 for item in symbols],
                      'hint': '没有字段 = 这一拍还没推送行情'})
    if action == 'depth':
        symbol = str(args.get('symbol') or '') or _current_symbol(desk)
        if not symbol:
            return _json({'ok': False, 'error': '给 symbol（盘口按合约订阅）'})
        return _json(_depth_table(desk, symbol,
                                  int(args.get('limit') or 5)))
    frame, meta = _market_frame(desk, args)
    if frame is None:
        return _json({'ok': False, **meta})
    table = _kline_rows(frame, limit)
    if action == 'klines':
        return _json({'ok': True, **meta, 'count': len(table['rows']),
                      'columns': table['columns'], 'rows': table['rows'],
                      'first': table['first'], 'last': table['last'],
                      'stats': table['stats'],
                      'hint': '趋势看 stats（涨跌幅 / 高低 / MA）；'
                              '指标数值用 action=indicator'})
    if action == 'indicator':
        data = _indicator_tables(desk, args, frame, meta)
        if not data.get('ok'):
            return _json({**data, **meta})
        return _json({'ok': True, **meta,
                      **{key: value for key, value in data.items()
                         if key != 'ok'}})
    if action in ('analysis', 'analyze', 'full'):
        # ★ 用户 2026-11-08：一次 K 线就把「结构 + 体检 + 形态 + 摘要」全算出来
        #   —— 比连调 levels / stats / patterns 省两次 IO，也比 desk_sequence
        #   少一轮模型往返 ✓
        limit_levels = max(20, min(int(args.get('limit') or 80), 400))
        back = max(10, min(int(args.get('limit') or 60), 500))
        table = _kline_rows(frame, back)
        levels = _pivot_levels(frame, limit_levels)
        stats = _stats_table(frame)
        patterns = _pattern_rows(frame, int(args.get('pattern_limit') or 6))
        digest = _market_digest(frame, meta)
        out: Dict[str, Any] = {
            'ok': True, **meta,
            'bars': table['stats'],
            'first': table['first'],
            'last': table['last'],
            'levels': {key: levels[key] for key in
                       ('last', 'swing', 'pivot_highs', 'pivot_lows', 'fib',
                        'volume_profile', 'support', 'resistance')
                       if key in levels},
            'stats': stats,
            'patterns': patterns,
            'text': digest.get('text'),
            'hint': '一次拿全套：levels 找价位、stats 看强弱、patterns 看形态；'
                    '要进一步下钻再单独调对应 action ✓',
        }
        symbol = str(meta.get('symbol') or meta.get('name') or '')
        if meta.get('source') == 'realtime':
            out['quote'] = _quote_row(desk, symbol)
            info = (getattr(desk, 'tabs', {}) or {}).get(symbol) or {}
            keys = [str((item or {}).get('key') or '')
                    for item in (info.get('indicators') or [])]
            out['indicators_on_chart'] = [key for key in keys if key]
            if out['indicators_on_chart']:
                data = _indicator_tables(
                    desk, {'keys': out['indicators_on_chart'], 'limit': 10},
                    frame, meta)
                out['indicator_values'] = data.get('items') or []
        if args.get('key') or args.get('keys'):
            data = _indicator_tables(desk, args, frame, meta)
            out['indicator_values'] = data.get('items') or []
        return _json(out)
    if action == 'levels':
        levels = _pivot_levels(frame, int(args.get('limit') or 80))
        return _json({'ok': True, **meta, **levels})
    if action == 'stats':
        return _json({'ok': True, **meta, 'stats': _stats_table(frame),
                      'bars': table['stats']})
    if action == 'patterns':
        rows = _pattern_rows(frame, int(args.get('limit') or 10))
        return _json({'ok': True, **meta, 'count': len(rows),
                      'patterns': rows,
                      'hint': 'tone: bull = 偏多，bear = 偏空 ✓'})
    if action == 'digest':
        return _json({**meta, **_market_digest(frame, meta)})
    # summary：报价 + K 线统计 + 图上指标（模型一问就有全套 ✓）
    symbol = str(meta.get('symbol') or meta.get('name') or '')
    out: Dict[str, Any] = {'ok': True, **meta, 'bars': table['stats'],
                           'first': table['first'], 'last': table['last']}
    if meta.get('source') == 'realtime':
        out['quote'] = _quote_row(desk, symbol)
        info = (getattr(desk, 'tabs', {}) or {}).get(symbol) or {}
        keys = [str((item or {}).get('key') or '')
                for item in (info.get('indicators') or [])]
        out['indicators_on_chart'] = [key for key in keys if key]
        if out['indicators_on_chart']:
            data = _indicator_tables(
                desk, {'keys': out['indicators_on_chart'], 'limit': 10},
                frame, meta)
            out['indicator_values'] = data.get('items') or []
    if args.get('key') or args.get('keys'):
        data = _indicator_tables(desk, args, frame, meta)
        out['indicator_values'] = data.get('items') or []
        if data.get('candidates'):
            out['candidates'] = data['candidates']
    out['next_hint'] = ('要更多根用 limit；要指定指标用 action=indicator；'
                        '图上指标 summary 会一起算')
    return _json(out)


def _call_screenshot(desk, args: Dict[str, Any]) -> str:
    """截图（请前端画一张 → 后端落盘 → 返回路径 ✓）"""
    import threading as _threading

    page = str(args.get('page') or '')
    name = str(args.get('name') or '')
    timeout = float(args.get('timeout') or 12)
    pending = getattr(desk, '_shot_pending', None)
    if pending is not None:
        return _json({'ok': False, 'error': '上一张截图还没回来，稍等一下'})
    event = _threading.Event()
    record = {'event': event, 'path': '', 'page': page}
    try:
        desk._shot_pending = record
        desk.push({'type': 'ui_action', 'action': 'screenshot',
                   'page': page, 'name': name})
        if not event.wait(max(1.0, timeout)):
            return _json({'ok': False,
                          'error': '截图超时（前端没响应；本地图表页开着吗？）'})
        path = str(record.get('path') or '')
        if not path:
            reason = str(record.get('error') or '').strip()
            return _json({'ok': False,
                          'error': f'截图失败：{reason}' if reason
                          else '截图失败（前端没有返回图片）',
                          'hint': '确认当前页是**图表页**（实时 / 本地图表）；'
                                  '在报价页 / 代码页没有图可截'})
        return _json({'ok': True, 'path': path, 'page': page})
    finally:
        desk._shot_pending = None


# ---------------------------------------------------------------- D 批（登录 / 账户 / 交易面板 / 预警）
def _call_login_futures(desk, args: Dict[str, Any]) -> str:
    """登录天勤（快期模拟 / 实盘）—— 密码只用于本次连接，不落盘 ✓"""
    username = str(args.get('username') or '').strip()
    password = str(args.get('password') or '')
    try:
        saved = desk.login_payload('futures') or {}
    except Exception:                                        # noqa: BLE001
        saved = {}
    if not username:
        username = str(saved.get('username') or '')
    if not password:
        password = str(saved.get('password') or '')
    if not username or not password:
        return _json({'ok': False, 'need_user_input': True,
                      'detail': '登录天勤需要**用户名 + 密码**（没有保存过）：'
                                '请让用户提供，或用「记住」填一次 ✓'})
    desk._on_connect_futures({
        'username': username, 'password': password,
        'real': bool(args.get('real')),
        'broker': str(args.get('broker') or ''),
        'account': str(args.get('account') or ''),
        'trade_password': str(args.get('trade_password') or ''),
        'remember': bool(args.get('remember')),
    })
    return _json({'ok': True, 'kind': 'futures',
                  'mode': '实盘' if args.get('real') else '快期模拟',
                  'message': '已发起登录（看运行日志 / 连接状态）'})


def _call_login_stock(desk, args: Dict[str, Any]) -> str:
    """连接富途 OpenD（模拟盘不需要账号，只要网关开着 ✓）"""
    desk._on_connect_stocks({
        'host': str(args.get('host') or ''),
        'port': args.get('port') or 0,
        'trd_env': str(args.get('trd_env') or 'SIMULATE').upper(),
        'trade': args.get('trade') if args.get('trade') is not None else True,
    })
    return _json({'ok': True, 'kind': 'stocks',
                  'env': str(args.get('trd_env') or 'SIMULATE').upper(),
                  'message': '已发起连接（先确认 FutuOpenD 已启动并登录 ✓）'})


def _call_account_kind(desk, args: Dict[str, Any]) -> str:
    """切换账户：快期模拟 / 富途模拟 / TqAccount 实盘（按页独立 ✓）"""
    key = str(args.get('key') or '').strip().lower()
    if not key:
        try:
            catalog = desk.account_catalog()
        except Exception:                                    # noqa: BLE001
            catalog = []
        return _json({'ok': False, 'error': '需要 key',
                      'available': [{'key': item.get('key'),
                                     'label': item.get('label'),
                                     'available': item.get('available')}
                                    for item in (catalog or [])]})
    page = str(args.get('page') or '')
    cell = args.get('cell')
    ok = desk.set_account_kind(key, page, cell)
    if not page:
        desk._on_set_account_kind({'key': key})
    return _json({'ok': bool(ok), 'key': key, 'page': page,
                  'message': '已切换' if ok else '这个账户不可用（先登录 / 开网关）'})


def _call_close_charts(desk, args: Dict[str, Any]) -> str:
    """关闭实时图表页：`all=true` 全关，或给 `symbols` 列表 ✓"""
    tabs = list((getattr(desk, 'tabs', {}) or {}).keys())
    wanted = [str(item) for item in (args.get('symbols') or []) if str(item)]
    if not args.get('all') and not wanted:
        return _json({'ok': False, 'error': '要 all=true 或给 symbols 列表',
                      'open': tabs[:20]})
    targets = tabs if args.get('all') else [item for item in wanted
                                            if item in tabs]
    for symbol in targets:
        desk._on_close_chart({'symbol': symbol})
    return _json({'ok': True, 'closed': targets, 'count': len(targets)})


def _call_theme(desk, args: Dict[str, Any]) -> str:
    """切换应用主题（深色 / 浅色）"""
    theme = str(args.get('theme') or '').lower()
    if theme not in ('dark', 'light'):
        return _json({'ok': False, 'error': 'theme 只能是 dark / light'})
    desk._on_set_setting({'key': 'app_theme', 'value': theme})
    return _json({'ok': True, 'theme': theme})


def _call_position_action(desk, args: Dict[str, Any]) -> str:
    """持仓行右键：平 / 反 / 全（市价）"""
    action = str(args.get('action') or '').lower()
    if action not in ('close', 'reverse', 'all', 'close_all'):
        return _json({'ok': False, 'error': 'action 只能是 close / reverse / all'})
    symbol = str(args.get('symbol') or '') or _current_symbol(desk)
    if not symbol:
        return _json({'ok': False, 'error': '需要 symbol（先打开一个图表）'})
    desk._on_position_action({'action': 'all' if action == 'close_all'
                              else action, 'symbol': symbol})
    return _json({'ok': True, 'action': action, 'symbol': symbol})


def _call_order_action(desk, args: Dict[str, Any]) -> str:
    """委托行右键：撤销某一笔 / 撤销该合约全部挂单 ✓"""
    action = str(args.get('action') or 'cancel').lower()
    symbol = str(args.get('symbol') or '') or _current_symbol(desk)
    if not symbol:
        return _json({'ok': False, 'error': '需要 symbol（先打开一个图表）'})
    if action == 'cancel':
        order_id = str(args.get('order_id') or '')
        if not order_id:
            return _json({'ok': False,
                          'error': '撤销单笔需要 order_id（先 desk_orders）'})
        desk._on_order_action({'action': 'cancel', 'symbol': symbol,
                               'order_id': order_id})
        return _json({'ok': True, 'cancelled': order_id, 'symbol': symbol})
    if action in ('cancel_all', 'all'):
        # ★ 先看**真实**挂单：没有就直接说没有（以前恒回 "cancelled: all"，
        #   用户/模型以为撤掉了 5 笔，其实柜台里一笔都没有 ✗）
        pending: List[Any] = []
        getter = getattr(desk, 'pending_orders', None)
        if callable(getter):
            try:
                pending = list(getter(symbol) or [])
            except Exception:                                # noqa: BLE001
                pending = []
        if not pending:
            return _json({'ok': True, 'cancelled': 0, 'symbol': symbol,
                          'message': '当前没有挂单（没有可撤的委托）'})
        desk._on_order_action({'action': 'cancel_all', 'symbol': symbol})
        return _json({'ok': True, 'cancelled': len(pending),
                      'symbol': symbol,
                      'message': f'已提交撤单 {len(pending)} 笔'})
    return _json({'ok': False, 'error': 'action 只能是 cancel / cancel_all'})


def _call_ticket_order(desk, args: Dict[str, Any]) -> str:
    """买卖盘一点下单（目标仓位 / 市价；买开 / 卖开 / 买平 / 卖平 ✓）"""
    symbol = str(args.get('symbol') or '') or _current_symbol(desk)
    side = str(args.get('side') or '').lower()
    if not symbol:
        return _json({'ok': False, 'error': '需要 symbol'})
    if side not in ('buy', 'sell'):
        return _json({'ok': False, 'error': 'side 只能是 buy / sell'})
    qty = int(args.get('qty') or args.get('volume') or 1)
    if qty <= 0:
        return _json({'ok': False, 'error': 'qty 必须是正整数'})
    if args.get('local'):
        desk._on_local_order({'symbol': symbol, 'side': side, 'qty': qty,
                              'volume': qty, 'price': args.get('price') or 0,
                              'offset': str(args.get('offset') or 'open')})
        return _json({'ok': True, 'symbol': symbol, 'side': side,
                      'qty': qty, 'account': 'local'})
    desk._on_ticket_order({'symbol': symbol, 'side': side, 'qty': qty,
                           'price': args.get('price')})
    return _json({'ok': True, 'symbol': symbol, 'side': side, 'qty': qty,
                  'message': '已按当前价下单（状态看 desk_orders）'})


def _call_alerts(desk, args: Dict[str, Any]) -> str:
    """列当前所有价格预警（只读）"""
    rows = []
    for item in (getattr(desk, 'alerts', []) or [])[:50]:
        rows.append({key: item.get(key) for key in
                     ('id', 'symbol', 'price', 'cross', 'action', 'qty',
                      'fired', 'account_label', 'message')})
    return _json({'ok': True, 'count': len(rows), 'items': rows})


def _call_add_alert(desk, args: Dict[str, Any]) -> str:
    """创建预警：价格到价 / **指标信号**（`kind:"signal"`, `key`, `op` ✓ v1.3.7-74）"""
    symbol = str(args.get('symbol') or '').strip()
    spec = args.get('signal')
    is_signal = (str(args.get('kind') or '').lower() == 'signal'
                 or isinstance(spec, dict))
    price = 0.0
    if not is_signal:
        try:
            price = float(args.get('price'))
        except (TypeError, ValueError):
            return _json({'ok': False, 'error': 'price 必须是数字'})
        if not symbol or price <= 0:
            return _json({'ok': False, 'error': '需要 symbol + price>0'})
    elif not symbol or not (args.get('key') or (isinstance(spec, dict)
                                                and spec.get('key'))):
        return _json({'ok': False,
                      'error': '信号预警需要 symbol + key（指标 key）'})
    action = str(args.get('action') or 'none')
    if action not in ('buy', 'sell', 'close', 'none', '买', '卖', '平'):
        return _json({'ok': False, 'error': 'action 只能是 buy/sell/close/none'})
    payload: Dict[str, Any] = {
        'symbol': symbol, 'price': price,
        'cross': str(args.get('cross') or '穿过'),
        'action': action,
        'qty': int(args.get('qty') or 1),
        'message': str(args.get('message') or ''),
        'expire': int(args.get('expire') or 0),
        'line': args.get('line') is not False,
        'page': str(args.get('page') or ''),
        'cell': args.get('cell'),
    }
    if is_signal:
        payload.update({'kind': 'signal', 'key': str(args.get('key') or ''),
                        'signal': dict(spec or {}),
                        'op': str(args.get('op') or 'buy').lower()})
    desk._on_add_alert(payload)
    if is_signal:
        return _json({'ok': True, 'symbol': symbol, 'kind': 'signal',
                      'key': payload.get('key'), 'op': payload.get('op'),
                      'message': '已加**指标信号**预警（信号变成 '
                                 + str(payload.get('op')).upper()
                                 + ' 时提醒 / 按动作下单）'})
    return _json({'ok': True, 'symbol': symbol, 'price': price,
                  'action': action,
                  'message': '已加预警（到价会提醒 / 按动作下单）'})


def _call_drop_alert(desk, args: Dict[str, Any]) -> str:
    """删除预警：给 id（来自 desk_alerts），或给 symbol（删该合约全部）✓"""
    alert_id = args.get('id')
    symbol = str(args.get('symbol') or '')
    if alert_id is None and not symbol and not args.get('all'):
        return _json({'ok': False,
                      'error': '给 id / symbol / all=true（先 desk_alerts）'})
    if args.get('all'):
        desk._on_clear_alerts({})
        return _json({'ok': True, 'removed': 'all'})
    if alert_id is not None:
        desk._on_drop_alert({'id': alert_id})
        return _json({'ok': True, 'removed': alert_id})
    keep = []
    removed = 0
    for item in list(getattr(desk, 'alerts', []) or []):
        if str(item.get('symbol') or '') == symbol:
            removed += 1
            continue
        keep.append(item)
    desk.alerts = keep
    desk._on_alerts({})
    return _json({'ok': True, 'removed': removed, 'symbol': symbol})


def _call_layouts_export(desk, args: Dict[str, Any]) -> str:
    """导出布局 JSON（可存文件 / 传给别的机器 ✓）"""
    from . import user_prefs as _prefs
    local = bool(args.get('local'))
    scope = 'local' if local else 'realtime'
    records = _prefs.layouts(scope)
    text = json.dumps({'layouts': records}, ensure_ascii=False, indent=2)
    path = ''
    if args.get('path'):
        path = str(args.get('path'))
        try:
            with open(path, 'w', encoding='utf-8') as handle:
                handle.write(text)
        except OSError as error:
            return _json({'ok': False, 'error': f'写文件失败：{error}'})
    return _json({'ok': True, 'scope': scope, 'count': len(records),
                  'path': path, 'text': text[:12000]})


# ---------------------------------------------------------------- E 批（前端动作）
def _call_close_tabs(desk, args: Dict[str, Any]) -> str:
    kind = str(args.get('kind') or 'page').lower()
    if kind not in ('page', 'editor', 'pi'):
        return _json({'ok': False,
                      'error': 'kind 只能是 page / editor / pi'})
    ids = [str(item) for item in (args.get('ids') or []) if str(item)]
    all_tabs = args.get('all') is True
    if not all_tabs and not ids:
        return _json({'ok': False,
                      'error': '要 all=true 或给 ids 列表（别误关全部 ✓）'})
    desk.push({'type': 'ui_action', 'action': 'close_tabs',
               'kind': kind, 'ids': ids, 'all': all_tabs})
    return _json({'ok': True, 'kind': kind, 'ids': ids, 'all': all_tabs})


def _call_open_ui(desk, args: Dict[str, Any]) -> str:
    target = str(args.get('target') or '').lower()
    if target == 'book':
        # 二级报价面板（右侧 5 档）—— 和 `desk_book{action:"open"}` 等价 ✓
        return _call_book(desk, {'action': 'open'})
    # ★ v1.3.7-83：四个扩展页也能从 PI 打开 ✓
    allowed = {'logs', 'settings', 'palette', 'home', 'quote', 'workspace',
               'research', 'login', 'book', 'info', 'workbench', 'datahub',
               'ops', 'schedule'}
    if target not in allowed:
        return _json({'ok': False,
                      'error': f'target 只能是 {sorted(allowed)}'})
    payload = {'type': 'ui_action', 'action': 'open_ui', 'target': target}
    if args.get('section'):
        payload['section'] = str(args.get('section'))
    if args.get('login'):
        payload['login'] = str(args.get('login'))
    desk.push(payload)
    return _json({'ok': True, 'opened': target})



# ---------------------------------------------------------------- F 批（数据 / 运维 / 研究 / 工作台）
def _frame_rows(frame, limit: int = 50) -> List[Dict[str, Any]]:
    """DataFrame 前 N 行 → 可 JSON 的记录 ✓"""
    try:
        head = frame.head(int(limit))
        return json.loads(head.to_json(orient='records', date_format='iso'))
    except Exception:                                        # noqa: BLE001
        try:
            return [dict(row) for row in frame.head(int(limit)).to_dict(
                'records')]
        except Exception:                                    # noqa: BLE001
            return []


def _call_datahub_list(desk, args: Dict[str, Any]) -> str:
    """本地数据平台：所有数据文件（名字 / 行数 / 周期 ✓）"""
    hub = desk.datahub_view() if hasattr(desk, 'datahub_view') else None
    if hub is None:
        return _json({'ok': False, 'error': '本地数据平台不可用'})
    items = []
    for row in (hub.items() or [])[:60]:
        items.append({key: row.get(key) for key in
                      ('name', 'rows', 'symbol', 'duration', 'path')
                      if key in row})
    return _json({'ok': True, 'count': len(items), 'items': items})


def _call_datahub_query(desk, args: Dict[str, Any]) -> str:
    """在数据平台里跑 SQL（表名 = 数据名，如 `select * from test limit 5`）"""
    sql = str(args.get('sql') or '').strip()
    if not sql:
        return _json({'ok': False, 'error': '需要 sql（表名 = 数据名）'})
    hub = desk.datahub_view() if hasattr(desk, 'datahub_view') else None
    if hub is None:
        return _json({'ok': False, 'error': '本地数据平台不可用'})
    try:
        rows = hub.query(sql, limit=int(args.get('limit') or 200))
    except Exception as error:                               # noqa: BLE001
        return _json({'ok': False, 'error': f'查询失败：{error}'})
    return _json({'ok': True, 'count': len(rows or []),
                  'rows': (rows or [])[:100]})


def _call_datahub_preview(desk, args: Dict[str, Any]) -> str:
    """预览 / 重采样某个数据集（`rule` 给了就重采样 ✓）"""
    name = str(args.get('name') or '').strip()
    if not name:
        return _json({'ok': False, 'error': '需要 name（先 desk_datahub_list）'})
    hub = desk.datahub_view() if hasattr(desk, 'datahub_view') else None
    if hub is None:
        return _json({'ok': False, 'error': '本地数据平台不可用'})
    try:
        rule = str(args.get('rule') or '').strip()
        frame = hub.resample(name, rule) if rule else hub.load(name)
    except Exception as error:                               # noqa: BLE001
        return _json({'ok': False, 'error': f'读取失败：{error}'})
    rows = _frame_rows(frame, int(args.get('limit') or 20))
    return _json({'ok': True, 'name': name, 'rule': rule or '',
                  'rows': len(frame), 'head': rows})


def _call_datahub_quality(desk, args: Dict[str, Any]) -> str:
    """数据质量报告（缺口 / 重复 / 异常 ✓）"""
    name = str(args.get('name') or '').strip()
    if not name:
        return _json({'ok': False, 'error': '需要 name'})
    hub = desk.datahub_view() if hasattr(desk, 'datahub_view') else None
    if hub is None:
        return _json({'ok': False, 'error': '本地数据平台不可用'})
    try:
        report = hub.quality(name)
    except Exception as error:                               # noqa: BLE001
        return _json({'ok': False, 'error': f'体检失败：{error}'})
    return _json({'ok': True, 'name': name, 'report': report})


def _call_ops_tokens(desk, args: Dict[str, Any]) -> str:
    """平台令牌列表（只读，不含明文 token ✓）"""
    ops = desk.ops_view() if hasattr(desk, 'ops_view') else None
    if ops is None:
        return _json({'ok': False, 'error': '运维服务不可用'})
    rows = []
    for row in (ops.tokens.items() or [])[:40]:
        rows.append({key: row.get(key) for key in
                     ('id', 'name', 'scopes', 'created', 'revoked')
                     if key in row})
    return _json({'ok': True, 'count': len(rows), 'items': rows})


def _call_ops_token_issue(desk, args: Dict[str, Any]) -> str:
    """签发平台令牌（返回明文 token，**只显示一次** ✓）"""
    ops = desk.ops_view() if hasattr(desk, 'ops_view') else None
    if ops is None:
        return _json({'ok': False, 'error': '运维服务不可用'})
    scopes = args.get('scopes') or ['read']
    if isinstance(scopes, str):
        scopes = [item.strip() for item in scopes.split(',') if item.strip()]
    token = ops.tokens.issue(str(args.get('name') or 'pi'), scopes=scopes)
    return _json({'ok': True, 'token': token,
                  'note': '这个 token 只显示这一次，请让用户自己保存 ✓'})


def _ops_spec(args: Dict[str, Any]) -> Dict[str, Any]:
    """把工具参数整理成任务定义（trigger / action / guard ✓）"""
    kind = str(args.get('trigger') or args.get('trigger_kind')
               or 'interval').lower()
    trigger: Dict[str, Any] = {'kind': kind}
    if kind == 'daily':
        trigger['at'] = str(args.get('at') or '09:00')
        trigger['days'] = str(args.get('days') or 'mon-fri')
    elif kind == 'interval':
        trigger['every'] = max(1, int(args.get('every') or args.get('interval')
                                      or 300))
    elif kind == 'after':
        after = args.get('after') or args.get('deps') or ''
        if isinstance(after, str):
            after = [item.strip() for item in after.split(',') if item.strip()]
        trigger['after'] = [str(item) for item in after]
    action_kind = str(args.get('action_kind')
                      or args.get('kind') or 'tool').lower()
    action: Dict[str, Any] = {'kind': action_kind}
    if action_kind == 'tool':
        action['tool'] = str(args.get('tool') or '')
        raw = args.get('args')
        if isinstance(raw, str):
            try:
                import json as _jsonlib
                raw = _jsonlib.loads(raw) if raw.strip() else {}
            except Exception:                                # noqa: BLE001
                raw = {}
        action['args'] = dict(raw or {})
        if args.get('allow_dangerous'):
            action['allow_dangerous'] = True
    elif action_kind == 'sequence':
        raw_steps = args.get('steps')
        if isinstance(raw_steps, str):
            try:
                import json as _jsonlib
                raw_steps = _jsonlib.loads(raw_steps) if raw_steps.strip() else []
            except Exception:                                # noqa: BLE001
                raw_steps = []
        action['steps'] = [dict(item) for item in (raw_steps or [])
                           if isinstance(item, dict)]
    elif action_kind == 'ai':
        action['prompt'] = str(args.get('prompt') or '')
        action['allow_write'] = bool(args.get('allow_write'))
        if args.get('model'):
            action['model'] = str(args.get('model'))
    else:
        action['name'] = str(args.get('builtin') or 'heartbeat')
    guard: Dict[str, Any] = {}
    for key in ('skip_if_running', 'only_trading_hours', 'skip_holidays'):
        if key in args:
            guard[key] = bool(args.get(key))
    if 'max_runs_per_day' in args:
        guard['max_runs_per_day'] = int(args.get('max_runs_per_day') or 0)
    if 'retries' in args:
        guard['retries'] = max(0, min(5, int(args.get('retries') or 0)))
    if 'catch_up' in args:
        guard['catch_up'] = bool(args.get('catch_up'))
    depends = args.get('depends_on') or args.get('depends') or ''
    if isinstance(depends, str):
        depends = [item.strip() for item in depends.split(',') if item.strip()]
    if depends:
        guard['depends_on'] = [str(item) for item in depends]
    if 'depends_window' in args:
        guard['depends_window'] = int(args.get('depends_window') or 86400)
    when = args.get('when')
    if isinstance(when, str):
        try:
            import json as _jsonlib
            when = _jsonlib.loads(when) if when.strip() else {}
        except Exception:                                    # noqa: BLE001
            when = {}
    return {'name': str(args.get('name') or '').strip(), 'trigger': trigger,
            'action': action, 'guard': guard, 'when': dict(when or {}),
            'notify': str(args.get('notify') or 'error'),
            'enabled': bool(args.get('enabled')),
            'description': str(args.get('description') or '')}


def _task_row(task: Dict[str, Any]) -> Dict[str, Any]:
    trigger = task.get('trigger') or {}
    action = task.get('action') or {}
    if trigger.get('kind') == 'interval':
        when = f"每 {trigger.get('every')}s"
    elif trigger.get('kind') == 'daily':
        when = f"每天 {trigger.get('at')}（{trigger.get('days')}）"
    elif trigger.get('kind') == 'after':
        when = '成功前置任务后：' + '、'.join(trigger.get('after') or [])
    else:
        when = '仅手动'
    guard = task.get('guard') or {}
    depends = guard.get('depends_on') or []
    what = str(action.get('kind') or 'builtin')
    if what == 'tool':
        what = 'tool:' + str(action.get('tool') or '')
    elif what == 'ai':
        what = 'ai'
    elif what == 'sequence':
        what = f"sequence:{len(action.get('steps') or [])} 步"
    else:
        what = 'builtin:' + str(action.get('name') or '')
    condition = task.get('when') or {}
    return {'name': task.get('name'), 'when': when, 'what': what,
            'depends_on': list(depends),
            'if': (f"{condition.get('tool')} {condition.get('path') or ''}"
                   f" {condition.get('op') or ''} {condition.get('value')}"
                   if condition.get('tool') else ''),
            'enabled': bool(task.get('enabled')),
            'notify': task.get('notify') or 'error',
            'last_status': task.get('last_status'),
            'last_error': str(task.get('last_error') or '')[:120],
            'runs': task.get('runs'), 'errors': task.get('errors'),
            'next_run': task.get('next_run'),
            'description': task.get('description') or ''}


def _call_ops_tasks(desk, args: Dict[str, Any]) -> str:
    """定时任务列表（触发 + 动作 + 上次结果 ✓）"""
    ops = desk.ops_view() if hasattr(desk, 'ops_view') else None
    if ops is None:
        return _json({'ok': False, 'error': '运维服务不可用'})
    rows = [_task_row(row) for row in (ops.tasks.items() or [])[:40]]
    getter = getattr(ops.tasks, 'snapshot', None)      # 兼容老 / 假实现 ✓
    snap = getter() if callable(getter) else {}
    enabled_fn = getattr(ops, 'scheduler_enabled', None)
    scheduler_on = bool(enabled_fn()) if callable(enabled_fn) else True
    return _json({'ok': True, 'count': len(rows), 'items': rows,
                  'enable': scheduler_on,
                  'builtins': snap.get('builtins') or [],
                  'holidays': snap.get('holidays') or [],
                  'hint': ('要新建：desk_ops{action:"task_add", name, '
                           'kind:"tool"|"ai", tool / prompt, '
                           'trigger:"interval"|"daily", every / at}')})


def _call_ops_task_add(desk, args: Dict[str, Any]) -> str:
    """新建定时任务（动作可以是 MCP 工具 / AI 提示词 / 内置 ✓）"""
    ops = desk.ops_view() if hasattr(desk, 'ops_view') else None
    if ops is None:
        return _json({'ok': False, 'error': '运维服务不可用'})
    spec = _ops_spec(args)
    if not spec['name']:
        return _json({'ok': False, 'error': '需要 name（任务名）'})
    if spec['action']['kind'] == 'tool' and not spec['action'].get('tool'):
        return _json({'ok': False, 'error': 'kind=tool 需要 tool（工具名，'
                                            '先 desk_ops{action:"tasks"} 看能用哪些）'})
    if spec['action']['kind'] == 'ai' and not spec['action'].get('prompt'):
        return _json({'ok': False, 'error': 'kind=ai 需要 prompt（提示词）'})
    try:
        ops.tasks.add(spec['name'],
                      int(spec['trigger'].get('every') or 300), '',
                      trigger=spec['trigger'], guard=spec['guard'],
                      enabled=spec['enabled'], notify=spec['notify'],
                      description=spec['description'])
        task = ops.tasks.update(spec['name'], action=spec['action'],
                                trigger=spec['trigger'], guard=spec['guard'])
    except Exception as error:                               # noqa: BLE001
        return _json({'ok': False, 'error': f'新建失败：{error}'})
    return _json({'ok': True, 'task': _task_row(task),
                  'note': ('已启用 ✓' if spec['enabled']
                           else '默认停用：要跑得先 desk_ops{action:"task_toggle",'
                                ' name, on:true}')})


def _call_ops_task_update(desk, args: Dict[str, Any]) -> str:
    """改定时任务（触发 / 动作 / 保护 / 启停 ✓）"""
    ops = desk.ops_view() if hasattr(desk, 'ops_view') else None
    if ops is None:
        return _json({'ok': False, 'error': '运维服务不可用'})
    spec = _ops_spec(args)
    if not spec['name']:
        return _json({'ok': False, 'error': '需要 name'})
    fields: Dict[str, Any] = {'trigger': spec['trigger'],
                              'guard': spec['guard'],
                              'enabled': spec['enabled']}
    if spec['action'].get('kind') in ('tool', 'ai', 'builtin'):
        fields['action'] = spec['action']
    try:
        task = ops.tasks.update(spec['name'], **fields)
    except Exception as error:                               # noqa: BLE001
        return _json({'ok': False, 'error': f'修改失败：{error}'})
    return _json({'ok': True, 'task': _task_row(task)})


def _call_ops_task_remove(desk, args: Dict[str, Any]) -> str:
    """删掉一个定时任务"""
    ops = desk.ops_view() if hasattr(desk, 'ops_view') else None
    if ops is None:
        return _json({'ok': False, 'error': '运维服务不可用'})
    name = str(args.get('name') or '').strip()
    if not name:
        return _json({'ok': False, 'error': '需要 name'})
    return _json({'ok': bool(ops.tasks.remove(name)), 'name': name})


def _call_ops_alert_log(desk, args: Dict[str, Any]) -> str:
    """告警记录：按关键词 / 等级 / 规则查历史（告警中心 ✓ v1.3.7-97）"""
    ops = desk.ops_view() if hasattr(desk, 'ops_view') else None
    if ops is None:
        return _json({'ok': False, 'error': '运维服务不可用'})
    store = getattr(ops, 'alert_log', None)
    if store is None:
        return _json({'ok': False, 'error': '当前版本没有告警记录'})
    mode = str(args.get('mode') or 'list').lower()
    if mode == 'clear':
        return _json({'ok': True, 'cleared': store.clear()})
    result = store.query(str(args.get('query') or ''),
                         str(args.get('level') or ''),
                         str(args.get('rule') or ''),
                         int(args.get('limit') or 20),
                         int(args.get('offset') or 0))
    return _json({'ok': True, 'total': result['total'],
                  'items': [{key: row.get(key) for key in
                             ('ts', 'rule', 'level', 'title', 'text',
                              'channel', 'ok', 'symbol')}
                            for row in result['items']],
                  'stats': store.stats(),
                  'daily': store.daily(int(args.get('days') or 14)),
                  'hint': '按时间倒序；channel 里 quiet(静默) = 被静默时段压制'})


def _call_ops_equity(desk, args: Dict[str, Any]) -> str:
    """账户净值 / 回撤（近 N 天，含曲线点 ✓ v1.3.7-95）"""
    ops = desk.ops_view() if hasattr(desk, 'ops_view') else None
    if ops is None:
        return _json({'ok': False, 'error': '运维服务不可用'})
    store = getattr(ops, 'equity', None)
    if store is None:
        return _json({'ok': False, 'error': '当前版本没有净值序列'})
    days = int(args.get('days') or 30)
    keys = list(getattr(ops, 'equity_keys', []) or []) or ['account']
    key = str(args.get('key') or keys[0])
    stats = store.stats(key, days)
    return _json({'ok': True, 'key': key, 'keys': keys,
                  'stats': {k: v for k, v in stats.items()
                            if k != 'points_list'},
                  'points': stats.get('points_list') or [],
                  'note': ('净值每 60 秒采一条；回撤告警 strategy_drawdown '
                           '就用这条序列（重启不丢峰值）')})


def _call_ops_alert_rules(desk, args: Dict[str, Any]) -> str:
    """告警规则：list / save / reset（哪些事推手机 ✓ v1.3.7-92）"""
    ops = desk.ops_view() if hasattr(desk, 'ops_view') else None
    if ops is None:
        return _json({'ok': False, 'error': '运维服务不可用'})
    mode = str(args.get('mode') or args.get('action2') or 'list').lower()
    store = getattr(ops, 'alert_rules', None)
    if store is None:
        return _json({'ok': False, 'error': '当前版本不支持告警规则'})
    if mode in ('settings', 'save_settings'):
        quiet = args.get('quiet')
        digest = args.get('digest')
        if isinstance(quiet, str):
            try:
                quiet = json.loads(quiet) if quiet.strip() else {}
            except Exception:                                # noqa: BLE001
                quiet = {}
        if isinstance(digest, str):
            try:
                digest = json.loads(digest) if digest.strip() else {}
            except Exception:                                # noqa: BLE001
                digest = {}
        out = store.save_settings({'quiet': quiet or {},
                                   'digest': digest or {}})
        return _json({'ok': True, 'settings': out})
    if mode in ('save', 'reset'):
        if mode == 'reset':
            return _json({'ok': True, 'rules': store.reset(),
                          'note': '已恢复默认'})
        raw = args.get('rules')
        if isinstance(raw, str):
            try:
                raw = json.loads(raw) if raw.strip() else []
            except Exception:                                # noqa: BLE001
                raw = []
        if not isinstance(raw, list):
            return _json({'ok': False, 'error': 'rules 要是数组'})
        return _json({'ok': True, 'rules': store.save(raw)})
    rows = store.items()
    return _json({'ok': True, 'count': len(rows),
                  'settings': store.settings(),
                  'items': [{key: row.get(key) for key in
                             ('id', 'source', 'label', 'desc', 'enabled',
                              'level', 'min_interval')} for row in rows],
                  'hint': ('desk_ops{action:"alert_rules", mode:"save", '
                           'rules:[{"id":"trade_fill","enabled":true}]}')})


def _call_ops_notify_config(desk, args: Dict[str, Any]) -> str:
    """配置告警通道：wecom / **xtuis（公众号）** / email / webhook ✓"""
    ops = desk.ops_view() if hasattr(desk, 'ops_view') else None
    if ops is None:
        return _json({'ok': False, 'error': '运维服务不可用'})
    kind = str(args.get('kind') or 'wecom').lower()
    if kind not in ('wecom', 'xtuis', 'email', 'webhook'):
        return _json({'ok': False,
                      'error': 'kind 只能是 wecom / xtuis / email / webhook'})
    values = {key: value for key, value in args.items()
              if key not in ('kind', 'action', 'xtuis_token', 'xinxi_token')}
    for alias in ('xtuis_token', 'xinxi_token'):
        if args.get(alias):
            values['token'] = str(args.get(alias))
    if args.get('hook_url'):
        values['url'] = str(args.get('hook_url'))
    if not values:
        return _json({'ok': False, 'error': '需要至少一个字段（如 enabled / token）'})
    block = ops.notifier.configure(kind, values)
    return _json({'ok': True, 'kind': kind, 'values': block,
                  'hint': ('xtuis：关注公众号 `xtuis` → 回复 `token` 拿 token，'
                           '填进 token 就能在微信里收到告警')})


def _call_ops_notify_test(desk, args: Dict[str, Any]) -> str:
    """发一条测试告警（看每个通道的返回 ✓）"""
    ops = desk.ops_view() if hasattr(desk, 'ops_view') else None
    if ops is None:
        return _json({'ok': False, 'error': '运维服务不可用'})
    record = ops.notify(str(args.get('title') or 'minibt desk 测试告警'),
                        str(args.get('text') or '这是一条测试消息'), level='info')
    results = record.get('results') or []
    return _json({'ok': all(item.get('ok') for item in results),
                  'results': results})


def _call_ops_task_history(desk, args: Dict[str, Any]) -> str:
    """定时任务执行历史（最近 50 条 ✓）"""
    ops = desk.ops_view() if hasattr(desk, 'ops_view') else None
    if ops is None:
        return _json({'ok': False, 'error': '运维服务不可用'})
    getter = getattr(ops.tasks, 'snapshot', None)
    snap = getter() if callable(getter) else {}
    rows = []
    for row in (snap.get('history') or [])[:int(args.get('limit') or 20)]:
        rows.append({key: row.get(key) for key in
                     ('name', 'at', 'ok', 'kind', 'skipped', 'error',
                      'summary', 'ms') if key in row})
    return _json({'ok': True, 'count': len(rows), 'items': rows})


def _call_ops_task_templates(desk, args: Dict[str, Any]) -> str:
    """任务模板库（开盘简报 / 收盘复盘 / 资讯刷新 …）"""
    ops = desk.ops_view() if hasattr(desk, 'ops_view') else None
    if ops is None:
        return _json({'ok': False, 'error': '运维服务不可用'})
    getter = getattr(ops, 'templates', None)
    rows = getter() if callable(getter) else []
    return _json({'ok': True, 'count': len(rows),
                  'items': [{'name': row.get('name'),
                             'desc': row.get('desc'),
                             'action': (row.get('action') or {}).get('kind'),
                             'trigger': row.get('trigger')}
                            for row in rows],
                  'hint': 'desk_ops{action:"task_from_template", '
                          'template:"开盘前简报", enabled:true}'})


def _call_ops_task_from_template(desk, args: Dict[str, Any]) -> str:
    """按模板新建任务（动作 / 触发 / 保护原样复制 ✓）"""
    ops = desk.ops_view() if hasattr(desk, 'ops_view') else None
    if ops is None:
        return _json({'ok': False, 'error': '运维服务不可用'})
    adder = getattr(ops, 'add_from_template', None)
    if not callable(adder):
        return _json({'ok': False, 'error': '当前版本不支持模板'})
    template = str(args.get('template') or args.get('name') or '')
    try:
        task = adder(template, str(args.get('task_name') or ''),
                     bool(args.get('enabled')))
    except Exception as error:                               # noqa: BLE001
        return _json({'ok': False, 'error': str(error)})
    return _json({'ok': True, 'task': _task_row(task),
                  'note': '建好后默认停用，确认没问题再 task_toggle 打开'})


def _call_ops_tasks_export(desk, args: Dict[str, Any]) -> str:
    """导出全部任务（JSON；备份 / 换机器 ✓）"""
    ops = desk.ops_view() if hasattr(desk, 'ops_view') else None
    if ops is None:
        return _json({'ok': False, 'error': '运维服务不可用'})
    getter = getattr(ops, 'export_tasks', None)
    if not callable(getter):
        return _json({'ok': False, 'error': '当前版本不支持导出'})
    data = getter()
    rows = data.get('tasks') if isinstance(data, dict) else data
    return _json({'ok': True, 'count': len(rows or []),
                  'json': json.dumps(data, ensure_ascii=False)})


def _call_ops_tasks_import(desk, args: Dict[str, Any]) -> str:
    """导入任务（`data` 是 JSON 文本；同名默认跳过 ✓）"""
    ops = desk.ops_view() if hasattr(desk, 'ops_view') else None
    if ops is None:
        return _json({'ok': False, 'error': '运维服务不可用'})
    payload = args.get('data') or args.get('json') or ''
    if not str(payload).strip():
        return _json({'ok': False, 'error': '需要 data（导出的 JSON）'})
    importer = getattr(ops, 'import_tasks', None)
    if not callable(importer):
        return _json({'ok': False, 'error': '当前版本不支持导入'})
    try:
        out = importer(payload, bool(args.get('overwrite')))
    except Exception as error:                               # noqa: BLE001
        return _json({'ok': False, 'error': f'导入失败：{error}'})
    return _json(out)


def _call_ops_holidays(desk, args: Dict[str, Any]) -> str:
    """手工休市日：list / add / remove / toggle（`skip_holidays` 用 ✓）"""
    ops = desk.ops_view() if hasattr(desk, 'ops_view') else None
    if ops is None:
        return _json({'ok': False, 'error': '运维服务不可用'})
    action = str(args.get('action2') or args.get('mode') or 'list').lower()
    day = str(args.get('day') or '')
    store = ops.tasks.holidays
    if action == 'add':
        store.add(day)
    elif action == 'remove':
        store.remove(day)
    elif action == 'toggle':
        store.toggle(day)
    return _json({'ok': True, 'days': store.items()})


def _call_ops_task_run(desk, args: Dict[str, Any]) -> str:
    """立刻跑一个定时任务（例如 heartbeat / prune ✓）"""
    name = str(args.get('name') or '').strip()
    if not name:
        return _json({'ok': False, 'error': '需要 name（先 desk_ops_tasks）'})
    ops = desk.ops_view() if hasattr(desk, 'ops_view') else None
    if ops is None:
        return _json({'ok': False, 'error': '运维服务不可用'})
    submit = getattr(ops, 'run_task', None)
    if callable(submit):
        out = submit(name)
        return _json({**out,
                      'note': ('已在后台执行，跑完看 desk_ops{action:"tasks"}'
                               ' 的 last_status / task_history ✓')})
    try:
        rows = ops.tasks.run(name)
    except Exception as error:                               # noqa: BLE001
        return _json({'ok': False, 'error': f'运行失败：{error}'})
    return _json({'ok': True, 'name': name, 'result': rows})


def _call_ops_task_toggle(desk, args: Dict[str, Any]) -> str:
    """启用 / 停用一个定时任务"""
    name = str(args.get('name') or '').strip()
    if not name:
        return _json({'ok': False, 'error': '需要 name'})
    on = args.get('on') is not False
    ops = desk.ops_view() if hasattr(desk, 'ops_view') else None
    if ops is None:
        return _json({'ok': False, 'error': '运维服务不可用'})
    ok = ops.tasks.enable(name, on)
    return _json({'ok': bool(ok), 'name': name, 'enabled': on})


#: ★ v1.3.7-82：**不允许**从 `desk_cmd` 直通的命令 ——
#: 这些要么动钱、要么能执行任意代码 / 改权限 / 删数据，必须走专用工具
#: （专用工具里有确认 / 二次校验 / 参数收敛 ✓）
CMD_BLOCK = {
    # 动钱 / 账户
    'order_modify', 'account_action', 'local_account_action',
    'local_strategy_trade', 'workbench_submit', 'workbench_cancel',
    'workbench_modify', 'workbench_close_partial', 'switch_account',
    'replay_price', 'sim_reset', 'local_reset',
    # 能执行任意代码 / 命令
    'repl_eval', 'terminal_system', 'debug_cmd', 'debug_start',
    # AI 循环 / 权限 / 凭据
    'ai_send', 'pi_send', 'ai_desk_save', 'pi_models_save', 'login_save',
    # 通知通道 / 令牌 / 版本回滚 / 批量导入
    'ops_notify_config', 'ops_token_revoke', 'ops_token_revoke_all',
    'ops_version_rollback', 'ops_task_import',
    # 删除类
    'delete_template', 'drop_personal', 'pi_delete', 'ai_delete',
    'export_remove', 'exports_clear', 'info_clear', 'local_remove_folder',
    'pi_skills_remove', 'pi_skills_install',
}


def _call_cmd(desk, args: Dict[str, Any]) -> str:
    """**通用命令直通**（白名单）：把前端那 170+ 条命令接给模型 ✓

    用途：切主题 / 打开页面 / 拉资讯 / 选策略 / 会话改名 / 截图… 这些
    "看得见但不值得单独做一个工具"的命令。

    * 只放行 `desk.commands()` 里真实注册的命令；
    * `CMD_BLOCK` 里的（下单 / 执行代码 / 改权限 / 删数据）**一律拒绝**，
      并告诉模型该用哪个专用工具；
    * 走 `desk.handle()` —— 与界面点击**完全同一条路径**（含审计 / 耗时日志 ✓）。
    """
    cmd = str(args.get('cmd') or '').strip()
    payload = args.get('args') or args.get('payload') or {}
    if not isinstance(payload, dict):
        return _json({'ok': False, 'error': 'args 要是一个对象（dict）'})
    if not cmd:
        table = desk.commands() if hasattr(desk, 'commands') else {}
        names = sorted(name for name in table if name not in CMD_BLOCK)
        return _json({'ok': False, 'error': '需要 cmd',
                      'examples': names[:20],
                      'count': len(names),
                      'hint': 'desk_cmd{cmd:"set_theme", args:{theme:"light"}}'})
    table = desk.commands() if hasattr(desk, 'commands') else {}
    if cmd not in table:
        import difflib
        names = [name for name in table if name not in CMD_BLOCK]
        close = difflib.get_close_matches(cmd, names, n=5, cutoff=0.6)
        if not close:
            close = difflib.get_close_matches(cmd, names, n=5, cutoff=0.4)
        return _json({'ok': False, 'error': f'没有这个命令：{cmd}',
                      'did_you_mean': close})
    if cmd in CMD_BLOCK:
        return _json({'ok': False, 'blocked': True, 'cmd': cmd,
                      'detail': ('这条命令会动钱 / 执行代码 / 改权限 / 删数据，'
                                 '不能直通；请用对应的专用工具'
                                 '（如 desk_order / desk_order_action / '
                                 'desk_position_action / desk_ops）')})
    try:
        from . import protocol as _protocol
        # 与界面点击**完全同一条路径**（含耗时日志 / 命令审计 ✓）
        desk.handle(_protocol.encode_command({'cmd': cmd,
                                              'payload': payload}))
        return _json({'ok': True, 'cmd': cmd, 'sent': True,
                      'note': '已执行（界面补丁已推送）'})
    except Exception as error:                               # noqa: BLE001
        return _json({'ok': False, 'cmd': cmd,
                      'error': f'{type(error).__name__}: {error}'})


def _call_local(desk, args: Dict[str, Any]) -> str:
    """本地图表单一入口（list / load / pages ✓）"""
    action = str(args.get('action') or 'list').lower()
    base = {key: value for key, value in args.items() if key != 'action'}
    if action == 'list':
        return _call_local_list(desk, base)
    if action == 'load':
        return _call_local_load(desk, base)
    if action == 'pages':
        return _call_local_pages(desk, base)
    return _json({'ok': False, 'error': 'action 只能是 list / load / pages'})


def _audit_orders(desk, limit: int = 30) -> List[Dict[str, Any]]:
    """最近的**委托审计**（工作台没打开 / 没记录 → 空列表 ✓）"""
    bench = getattr(desk, '_workbench', None)
    store = getattr(bench, 'store', None)
    reader = getattr(store, 'orders', None)
    if not callable(reader):
        return []
    try:
        rows = reader(int(limit))
    except Exception:                                        # noqa: BLE001
        return []
    return [dict(item) for item in (rows or [])][:int(limit)]


def _call_account(desk, args: Dict[str, Any]) -> str:
    """账户只读入口（summary / positions / orders / unfilled / trades /
    pending / audit ✓）"""
    action = str(args.get('action') or 'summary').lower()
    base = {key: value for key, value in args.items() if key != 'action'}
    if action == 'audit':
        rows = _audit_orders(desk, int(args.get('limit') or 30))
        return _json({'ok': True, 'orders': rows, 'count': len(rows),
                      'note': 'status 是**提交**状态（PENDING=已提交给柜台，'
                              'REJECTED=被拒），不是成交状态 ✓'})
    if action not in ('summary', 'positions', 'orders', 'unfilled', 'trades',
                      'pending'):
        return _json({'ok': False,
                      'error': 'action 只能是 summary / positions / orders / '
                               'unfilled / trades / pending / audit'})
    if action in ('positions', 'orders'):
        handler = _call_positions if action == 'positions' else _call_orders
        return handler(desk, base)
    data = _account_rows(desk, **_account_args(desk, base))
    body: Dict[str, Any] = {'ok': data.get('ok'),
                            'source': data.get('source'),
                            'symbol': data.get('symbol'),
                            'account': data.get('account', ''),
                            'login': data.get('login'),
                            'balance': data.get('balance'),
                            'labels': data.get('labels')}
    if not data.get('ok'):
        body['message'] = data.get('message', '')
        return _json(body)
    if action == 'summary':
        counts = {}
        for name in ('positions', 'orders', 'unfilled', 'trades'):
            block = data.get(name) or {}
            counts[name] = len(block.get('rows') or [])
        body['counts'] = counts
        body['message'] = ('账户已就绪' if (data.get('login') or {}).get(
            'ready') else '账户数据可读，但交易通道未就绪（下单会失败）')
        body['hint'] = ('下单前先确认 counts.unfilled 里没有同向重复挂单；'
                        '委托审计用 action:"audit"')
        return _json(body)
    block = data.get(action) or {}
    if action == 'pending':
        body['symbol'] = data.get('symbol')
        block = data.get('unfilled') or {}
        body['pending'] = block
        body['count'] = len(block.get('rows') or [])
        body['message'] = ('没有挂单' if not body['count']
                           else f"未成交 {body['count']} 笔")
        return _json(body)
    body[action] = block
    body['count'] = len(block.get('rows') or [])
    return _json(body)


def _call_research(desk, args: Dict[str, Any]) -> str:
    """研究平台单一入口（list / start / cancel ✓）"""
    action = str(args.get('action') or 'list').lower()
    base = {key: value for key, value in args.items() if key != 'action'}
    table = {'list': _call_research_list, 'start': _call_research_start,
             'cancel': _call_research_cancel}
    handler = table.get(action)
    if handler is None:
        return _json({'ok': False,
                      'error': 'action 只能是 list / start / cancel'})
    return handler(desk, base)


def _call_tv(desk, args: Dict[str, Any]) -> str:
    """「指标和策略」页单一入口（list / detail / source / star / live / script /
    reload ✓）"""
    action = str(args.get('action') or 'list').lower()
    base = {key: value for key, value in args.items() if key != 'action'}
    table = {'list': _call_tv_list, 'detail': _call_tv_detail,
             'source': _call_tv_source, 'star': _call_tv_star,
             'live': _call_tv_live, 'script': _call_tv_script,
             'reload': _call_tv_reload}
    handler = table.get(action)
    if handler is None:
        return _json({'ok': False,
                      'error': 'action 只能是 ' + ' / '.join(table)})
    return handler(desk, base)


def _call_datahub(desk, args: Dict[str, Any]) -> str:
    """数据平台单一入口（list / query / preview / quality ✓）"""
    action = str(args.get('action') or 'list').lower()
    base = {key: value for key, value in args.items() if key != 'action'}
    table = {'list': _call_datahub_list, 'query': _call_datahub_query,
             'preview': _call_datahub_preview,
             'quality': _call_datahub_quality}
    handler = table.get(action)
    if handler is None:
        return _json({'ok': False,
                      'error': 'action 只能是 ' + ' / '.join(table)})
    return handler(desk, base)


def _call_ops(desk, args: Dict[str, Any]) -> str:
    """运维单一入口（tokens / tasks / task_add / task_run / holidays ✓）"""
    action = str(args.get('action') or 'tokens').lower()
    base = {key: value for key, value in args.items() if key != 'action'}
    table = {'tokens': _call_ops_tokens,
             'token_issue': _call_ops_token_issue,
             'tasks': _call_ops_tasks, 'task_run': _call_ops_task_run,
             'task_toggle': _call_ops_task_toggle,
             # ★ v1.3.7-79：定时任务（工具 / AI 动作，落盘 ✓）
             'task_add': _call_ops_task_add,
             'task_update': _call_ops_task_update,
             'task_remove': _call_ops_task_remove,
             'task_history': _call_ops_task_history,
             'notify_config': _call_ops_notify_config,
             'alert_rules': _call_ops_alert_rules,
             'equity': _call_ops_equity,
             'alert_log': _call_ops_alert_log,
             'notify_test': _call_ops_notify_test,
             'task_templates': _call_ops_task_templates,
             'task_from_template': _call_ops_task_from_template,
             'tasks_export': _call_ops_tasks_export,
             'tasks_import': _call_ops_tasks_import,
             'holidays': _call_ops_holidays}
    handler = table.get(action)
    if handler is None:
        return _json({'ok': False,
                      'error': 'action 只能是 ' + ' / '.join(table)})
    return handler(desk, base)


def _call_research_list(desk, args: Dict[str, Any]) -> str:
    """研究平台的实验列表（只读 ✓）"""
    lab = desk.research_view() if hasattr(desk, 'research_view') else None
    if lab is None:
        return _json({'ok': False, 'error': '研究平台不可用'})
    try:
        rows = lab.store.experiments(int(args.get('limit') or 20))
    except Exception as error:                               # noqa: BLE001
        return _json({'ok': False, 'error': f'读取失败：{error}'})
    return _json({'ok': True, 'count': len(rows or []),
                  'items': (rows or [])[:20]})


def _call_research_start(desk, args: Dict[str, Any]) -> str:
    """启动研究任务（参数优化 / Walk-Forward / 网格 / 批量）"""
    strategy = str(args.get('strategy') or '').strip()
    if not strategy:
        return _json({'ok': False, 'error': '需要 strategy（.py 路径）'})
    if not os.path.isfile(strategy):
        return _json({'ok': False, 'error': f'策略文件不存在：{strategy}'})
    lab = desk.research_view() if hasattr(desk, 'research_view') else None
    if lab is None:
        return _json({'ok': False, 'error': '研究平台不可用'})
    payload = {'strategy': strategy, 'mode': str(args.get('mode')
                                                 or 'grid')}
    for key in ('symbols', 'params', 'files', 'windows', 'metrics'):
        if args.get(key) is not None:
            payload[key] = args.get(key)
    lab.start(payload)
    return _json({'ok': True, 'strategy': strategy,
                  'mode': payload['mode'],
                  'message': '研究任务已开始（进度看「研究」页 ✓）'})


def _call_research_cancel(desk, args: Dict[str, Any]) -> str:
    lab = desk.research_view() if hasattr(desk, 'research_view') else None
    if lab is None:
        return _json({'ok': False, 'error': '研究平台不可用'})
    lab.cancel()
    return _json({'ok': True, 'cancelled': True})


def _call_workbench_snapshot(desk, args: Dict[str, Any]) -> str:
    """交易工作台快照：订单票 / 持仓 / 挂单 / 风控（只读 ✓）"""
    bench = desk.workbench_view() if hasattr(
        desk, 'workbench_view') else None
    if bench is None:
        return _json({'ok': False, 'error': '交易工作台不可用'})
    try:
        snap = bench.snapshot()
    except Exception as error:                               # noqa: BLE001
        return _json({'ok': False, 'error': f'读取失败：{error}'})
    if isinstance(snap, dict):
        snap = {key: snap.get(key) for key in
                ('ticket', 'limits', 'positions', 'orders', 'audit', 'text')
                if key in snap}
    return _json({'ok': True, 'snapshot': snap})


def _call_workbench_limits(desk, args: Dict[str, Any]) -> str:
    """设置工作台风控（最大手数 / 单笔金额 / 日内笔数…）"""
    bench = desk.workbench_view() if hasattr(
        desk, 'workbench_view') else None
    if bench is None:
        return _json({'ok': False, 'error': '交易工作台不可用'})
    limits = args.get('limits') if isinstance(args.get('limits'), dict) else {
        key: args.get(key) for key in
        ('enabled', 'max_volume', 'max_notional', 'max_orders')
        if args.get(key) is not None}
    if not limits:
        return _json({'ok': False, 'error': '需要 limits（至少给一个字段）'})
    result = bench.configure(limits)
    return _json({'ok': True, 'limits': result})

def _slug(value: str) -> str:
    return re.sub(r'[^0-9A-Za-z_.-]+', '-', str(value or '')) or 'chart'
