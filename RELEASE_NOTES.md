# minibt 1.3.7 发布说明

**发布版本**：`1.3.7`
**发布日期**：2026-11-11
**Python**：>= 3.12
**许可证**：MIT
**依赖**：`pylightcharts>=0.2.1`（下限已跟着升）；**本版配套 `pylightcharts 0.2.1`**
（desk 前端改动全在那边 —— 告警中心 / 定时任务页 / PI 助手 / TA 悬浮标签）

## 一句话

1.3.7 是 **desk（交易终端）+ PI 助手** 的一整轮迭代（2026-11-08 ~ 11-11，
**110 轮**用户反馈 / 自查，`v1.3.7-1 ~ -110`）：先把「`import minibt` 直接崩」
和「指标目录少了很多」修死；把**编辑器**按性价比补齐；做出**零 npm 的 PI 助手
+ MCP 工具桥**（72 个工具，AI 能直接操控 desk）；最后用**资讯中心 / 告警中心 /
定时任务 v2** 把终端做成"能自己盯盘"的东西。

## 升级怎么做

```bash
# 两个包一起升（前端在 pylightcharts 里）
pip install -U minibt==1.3.7
pip install -U pylightcharts==0.2.1
minibt desk --check        # 自检（GBK 控制台也不会再抛 UnicodeEncodeError）
```

* 只升 `minibt` 也能跑，但 desk 的新界面（告警中心 / 定时任务页 / PI 界面 /
  TA 标签 / 换合约旧线清理）需要 `pylightcharts 0.2.1` 的 `desk.js`；
* 首次启动会重建指标目录缓存（`CATALOG_SCHEMA` 7 → 8 + 源码指纹），
  时间略长属正常；
* 桌面端配置都在 `~/.minibt/`（`desk/ops/`、`ai/`、`data/info.db`），
  不随升级删除。

## 本版做了什么（按块）

### 1. 阻断级修复

| 问题 | 状态 |
| --- | --- |
| `import minibt` 直接崩（`tulip` / `pine` / `talib` / `pair` 用了 `LineStyle` / `np` / `pd` 但只 `import TYPE_CHECKING`） | 已修 |
| 「指标目录少了很多」 | 缓存戳加 `minibt/indicators/*.py` **源码指纹** + 新增 `missing_indicators()` 自查 + TuLip 13 个纯数学算子归入 `NON_KLINE` → **有效指标 86 → 73，一个不缺** |
| `RollingVolumeProfile` 未导出（用户脚本 `class X(RollingVolumeProfile)` 被静默跳过） | 已导出 |

### 2. 编辑器

12 项按性价比补齐（多光标 / 折叠 / 查找替换 / 大纲 / 面包屑 / 函数签名 /
格式化 / 光标历史 …）+ **断点调试 / REPL / 代码片段 / 符号搜索**；
编辑器里的策略可直接送去 desk 回测、也能让 AI 改。

### 3. PI 助手（**零 npm**）

* 内置 PI 面板：对话、会话列表 / 目录切换 / 分屏 / 分支、思考折叠、用量、
  圆点导航（悬停显示「问：… / 答：…」）、Markdown（含 GFM 表格）；
* **独立界面**（对话 + 编辑代码，不依赖图表）、**悬浮窗**（`F1`，贴边收起、
  浮到窗口外、`@文件`、附件上传、右键菜单）；
* 技能搜索 / 安装；模型保存与选择说清楚（PI `models.json` 优先，内置 AI 兜底）。

### 4. PI 操控 desk：MCP 工具桥

* **双通道**：本机桥（`127.0.0.1`）+ 标准 MCP 服务端，外部程序也能连；
* **72 个工具**：图表 / 编辑 / 交易 / 数据 / 研究 / 预警 / 布局 / 定时任务；
* **危险工具必须 `confirm=true`**（`desk_order` / `desk_position_action` /
  `desk_order_action` / `desk_ticket_order` / `desk_strategy_live(start)` …），
  缺了回 `need_confirm` + 中文理由；
* 两个开关：`ai_desk_allow`（默认开）/ `ai_desk_order`（默认关）；
* 每次调用写 `~/.minibt/ai/audit.jsonl`，`password / token / key` 一律 `***`；
* `desk_cmd{cmd,args}` 白名单直通 **275 条**命令（`CMD_BLOCK` 36 条危险命令拒绝，
  拼错有 `did_you_mean`）；
* **让模型一次选对**：系统提示规则 + 工具合并（87 → 72）+ `desk_sequence`
  （`$0.resolved` 引用 + 每步 `hint`）→ 早期 48 轮的任务 **1~2 轮**完成。

### 5. 资讯中心 / 标的资讯

* **资讯中心**：快讯（60s 自动刷）/ 要闻 / 财经日历 / 宏观 / 期货资料五分区；
  搜索走本地 FTS5；「只看自选·持仓」；AI 摘要按天缓存；
  条目**左键不动 / 双击原文 / 右键菜单**（打开原文 / 打开图表 / 复制 / 让 AI 分析）；
* **标的资讯**（`F10`）：多合约 pill 导航 + 4 个金融小插件
  （Company Profile / Fundamental Data / Technical Analysis / Top Stories）；
* **图上事件圆点**：只画这个标的的事件（股票=公告日、期货=品种相关日历），
  按天分组、悬停卡片；宏观日历**不上图**；
* 股票 **富途优先**（快照 / 资金流），AkShare 兜底（财务 / 公告）。

### 6. 告警体系

* **4 个通道**：企业微信 / **微信公众号 xtuis** / 邮件 / 通用 webhook；
* **16 条规则**（按交易 / 预警 / 行情 / 定时任务 / 持仓 / 策略 / 资讯 / 系统分组）：
  成交换手 / 拒单 / 价格预警 / 行情停更 / 任务失败 / 持仓风险 / 挂单超时 /
  登录掉线 / 策略上下线 / 策略异常 / 策略回撤 / 回测完成 / 优化完成 /
  宏观临近 / 资讯关键词 / 后台异常；
* 静默时段（跨零点）、每日汇总、自定义资讯关键词；
* **告警中心页**：按天时间轴、搜索、等级 / 规则筛选、**一键复现到图表**、
  近 14 天柱状图、清空；
* **原则**：只推 **本次运行里即时发生** 的事件（新闻首扫做基线、日历 `stale`
  不推、回撤 / 持仓风险只在刚破阈值推一次）。

### 7. 定时任务 v2（独立成页）

`interval / daily / manual / after(DAG)` 四种触发；`builtin / tool / ai /
sequence` 四种动作；`when` 前置条件；重试（0~5）、6 小时补跑、
防重入 / 每日上限 / 只在交易时段 / 跳过节假日（`holidays.json`）；
6 个模板、导入导出、任务级通知；**默认停用**，需手动开启。

### 8. 命令行

```bash
python -m minibt.desk.cli doctor          # 体检
python -m minibt.desk.cli status          # 状态
python -m minibt.desk.cli tasks           # 定时任务
python -m minibt.desk.cli rpc desk_status --json
```

token 三来源（`MINIBT_DESK_TOKEN` → `--token` → `--token-file`）；
403 / 400 / 连不上都翻成中文提示。

### 9. 图表 / 交易收尾

* 技术分析**悬浮标签**（固定图表右上角，悬停卡片列每个指标的看多 / 看空 / 中立
  与数值；设置项 `ta_badge` 可关）；
* TA **自定义模板**（多命名保存 / 启用 / 删除）+ 信号接通 K 线圆点与预警；
* 多布局每格独立周期、成交量分布 / 动态表格跟随、回顶按钮；
* **残留指标删不掉**的根因修复：`pending` 时只保留 `items ∪ pending_keys`，
  删除匹配忽略大小写与 `:线名` 后缀。

## 测试与验证

| 项 | 结果 |
| --- | --- |
| `pytest -k "desk or packaging or docs or signals"` | **2148 passed / 1 skipped**（两项历史失败已随教程路径修正归零） |
| `pytest tests/test_minibt_packaging.py` | 6 passed（版本 / 依赖 / 子包 / 扩展源码 / 教程编译 / 内置数据） |
| `vitest run`（jslib） | **146 passed** |
| `tsc --noEmit` | 干净 |
| `mkdocs build --strict`（minibt_docs） | 0 警告 |

## 已知问题

* 从 **sdist** 安装需要本地有 C/C++ 编译器（`setup.py` 现场编译 5 个 Cython 扩展）；
  没有编译器时用 wheel（Windows / Linux / macOS 的 `cp312` 轮子）。
* 四个扩展入口（工作台 / 研究 / 数据平台 / 运维）在界面上**注释关闭**
  （频率低 + 未完善）；定时任务页、告警中心页仍然开放，命令 / REST / MCP 工具都在。
* 定时任务默认**停用**，需要在界面上手动启用。

## 产物

```
minibt-1.3.7-cp312-cp312-win_amd64.whl
minibt-1.3.7.tar.gz
dist/SHA256SUMS.txt
```

`python -m twine check dist/*` → 两个产物均 **PASSED**。

## 相关文档

| 内容 | 位置 |
| --- | --- |
| 分轮次日志（简版） | [`CHANGELOG.md`](CHANGELOG.md) |
| 完整更新日志（110 小节，A~H 分组） | [`../minibt_docs/docs/changelog.md`](../minibt_docs/docs/changelog.md) |
| 资讯中心 / 标的资讯手册 | [`13.31_news_center.md`](../minibt_docs/docs/minibt_desk/manual/13.31_news_center.md) |
| 定时任务手册 | [`13.32_scheduler.md`](../minibt_docs/docs/minibt_desk/manual/13.32_scheduler.md) |
| PI / MCP 使用说明 | [`13.29_pi_mcp_usage.md`](../minibt_docs/docs/minibt_desk/manual/13.29_pi_mcp_usage.md) |
| 命令 ↔ 工具对照 | [`13.30_desk_command_tool_matrix.md`](../minibt_docs/docs/minibt_desk/manual/13.30_desk_command_tool_matrix.md) |
| 发布流程 | [`RELEASING.md`](RELEASING.md) |
