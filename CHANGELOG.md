# minibt 更新日志

本文件记录 **minibt Python 包** 的发布信息；完整的产品更新（含 desk / miniqt /
VS Code 扩展）请同时参考：

- 官网更新日志：<https://www.minibt.cn/changelog/>
- 仓库完整记录：`minibt_docs/docs/changelog.md`

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

> 现状口径（**v1.3.7-111 发版收口**，历史轮次里的数字保留当时原样）：
> **MCP 工具 72 个** · desk 命令 **275 条**（覆盖 227 / 🔒 只走专用工具 35 /
> 前端内部 13 / **待补 0**）· 测试 `-k "desk or packaging or docs or signals"`
> **2154 passed / 1 skipped**（两项历史失败已随教程路径修正归零）。
> 生成器：`python scripts/desk_tool_matrix.py --write`。

## [1.3.7] - 2026-11-11

> **一句话**：1.3.7 是 **desk（交易终端）+ PI 助手** 的一整轮迭代
> （2026-11-08 ~ 11-11，**110 轮**，`v1.3.7-1 ~ -110`）。先把「`import minibt`
> 直接崩」「指标目录少了很多」修死；再把**编辑器**按性价比补齐；然后做出
> **零 npm 的 PI 助手 + MCP 工具桥**（72 个工具，AI 能直接操控 desk）；
> 最后用**资讯中心 / 告警中心 / 定时任务 v2** 把终端做成"能自己盯盘"的东西。
> 本文件是分轮次的简版日志，完整版（按 A~H 分组、110 小节）在
> `minibt_docs/docs/changelog.md`。

> **本版已打包**：`__version__ = 1.3.7`（`pyproject.toml` / `__init__.py` /
> `README.md` 徽章三处一致，`tests/test_minibt_packaging.py` 校验）。
> 配套前端 **`pylightcharts 0.2.1`**（desk 的告警中心 / 定时任务页 / PI 助手 /
> TA 悬浮标签都在那边），建议先 `pip install -U pylightcharts==0.2.1` 再启动 desk。
> 产物：`minibt-1.3.7-cp312-cp312-win_amd64.whl` + `minibt-1.3.7.tar.gz`，
> `twine check` 双 PASSED，sha256 见 `dist/SHA256SUMS.txt`。

### 指标与框架

- **`import minibt` 崩溃（阻断级）**：`minibt/indicators/tulip.py` 与
  `pine.py` 在 `@tobtind(... line_dash=LineDash.vbar)` 里用了 `LineStyle` /
  `LineDash`，但只 `import TYPE_CHECKING` → `NameError: name 'LineStyle' is
  not defined`；`talib.py` 缺 `np`、`pair.py` 缺 `np` / `pd`。全部补齐，
  `import minibt` 恢复正常 ✓。
- **导出 `RollingVolumeProfile`**（`minibt/__init__.py` + `__all__`）：
  用户脚本 `class X(RollingVolumeProfile)` 以前 `NameError` 被 desk 静默跳过。
- **`NON_KLINE_INDICATORS`（TuLip）补 13 个纯数学算子**：
  `asin/atan/cos/cosh/lag/ln/log10/max/min/sin/sinh/tan/tanh`（和已有的
  `abs/exp/sqrt` 同类，不是可画的 K 线指标）→ 有效指标 86 → 73。

### desk：指标目录

- **缓存戳加源码指纹**：`_modules_fingerprint()`（`minibt/indicators/*.py`
  + `indicator_catalog.py` 的 mtime / 大小 → sha1 前 12 位）拼进
  `schema_stamp()`，`CATALOG_SCHEMA` **7 → 8**。同版本号里追加指标也会重建
  缓存（用户实测「内置指标少了很多」的根因 ✗）。
- **`missing_indicators()`**：以 `minibt.<库>` 里带 `@tobtind` 的方法为准、
  减去各库 `NON_KLINE_INDICATORS`，逐库返回差集；`Desk.audit_indicators()`
  在启动时写运行日志。
- **选择器二级筛选不再静默藏指标**：chip 带计数、提示被筛掉多少、
  新增「显示全部」按钮（抽 `_sectionRows()` / `_visibleRows()`）。
- **`imported_indicator_entries()` 排除框架导出类**：`from minibt import *`
  的文件不再被误判成一堆指标（同一性判断 `getattr(minibt, name) is obj`）。

### desk：右键菜单 / 预警 / 编辑器

- **原生右键菜单禁用范围扩到浮层**：`.pylc-ip-mask`（指标、衡量标准和策略）、
  `.pylc-tp-mask`、`.pylc-al-mask`、`.pylc-ss-mask`、`.desk-menu`；
  输入框 / 编辑器保留（复制粘贴要用 ✓）。
- **预警记住 `page` / `cell` / `account`**：本地图表 = `local`（本地模拟），
  实时图表 = 该页 / 该格当前账户（`kq` / `futu` / `real`）；`_alert_view()`
  带 `account_label`，创建 toast 写明「触发按 X 下单」。
- **`alert_fired` 带账户 + `Trading.account_scope()`**：前端按
  `account === 'local'` 走 `local_order`，否则 `place_order` 带 `account` →
  后端把下单目标钉在该账户上（切页不再串账户 ✗）。
- **本地图表预警触发动作真的执行**：按 `buy` / `sell` / `close` 走
  `local_order`，平仓按持仓方向；价格改取 `LocalSim.prices`
  （本地数据文件没有行情源，以前永远不触发）；`app.ts` 不再把实时页预警
  灌进本地图表。
- **编辑器工具栏「符号」→「预览」**（功能不变：跨文件符号搜索）。

### desk：编辑器（v1.3.7）

- **分屏**：工具栏「分屏」/ `Ctrl+\`，左右各一个文件（同一文件不会重复挂）。
- **未保存保护**：关标签确认；关 desk 由 `beforeunload`（浏览器壳）与
  `DeskWindow` 的 `QEvent.Type.Close` 过滤器 + `QMessageBox`（桌面端）兜底，
  后端用 `editor_dirty` 记住未保存清单；**切页面不提醒** ✓。
- **断点调试**：`minibt/desk/debugger.py` + `debug_worker.py`（`sys.settrace`
  子进程 + JSON 行协议）：断点 / 继续 / 单步 / 步入 / 步出 / 停止 + 表达式求值，
  `debug_state` 补丁带调用栈与局部变量。
- **终端**：`minibt/desk/terminal.py`（shell 子进程 + 流式输出 + 行输入，
  `terminal_open/input/signal/restart/close/system` 命令）；「AI 对话」
  按钮执行设置里的 `terminal_ai_command`（默认 `pi`）✓。
  **`minibt/desk/ai.py` 与 `ai_chat` 命令已删除**（用户要求：AI 对话
  改在终端里进行）。
- **Python REPL**：`minibt/desk/repl.py`（常驻子进程，自动 `from minibt import *`，
  打印最后一个表达式，20 秒超时重启，traceback 过滤内部帧）。
- **片段库 / 重命名 / 引用 / 对比 / 选区格式化 / 字号 / 补全**
  （`editor-snippets.ts` + `editor-bundle.ts` + `editor-panel.ts`）：
  12 个片段、LSP 重命名与引用、Git HEAD 对比（`_git_head_text`）、
  dedent→ruff→reindent 的选区格式化、字号 = 设置 × 界面缩放、
  两级前缀（`kline.pta.`）指标函数补全。
- **新增测试** `tests/test_minibt_desk_editor_tools.py`（17 个用例）：
  片段清单、分屏 / 未保存（含「切页面不提醒」断言）、断点调试端到端
  （暂停 / 求值 / 报错）、AI 提示词与无密钥错误、REPL 命名空间与 traceback、
  选区格式化、Git HEAD 读取接口。

- **测试环境**：`tests/conftest.py` 新增 session 级 fixture，把 desk 的
  `personal.CONFIG_FILE` / `PERSONAL_ROOT` / `local_data.STATE_FILE` /
  `user_prefs.PREFS_FILE` 指到 tmp —— 测试不再 `exec` 用户真实的
  `~/.minibt/personal/indicators/*.py`（那些脚本的临时文件操作会把
  pytest 的 capture 文件关掉，导致后续用例
  `ValueError: I/O operation on closed file` ✗）。

- **调试 / REPL / 对比入口三处体验问题（2026-11-08 用户反馈 ✓）**：
  - 断点调试：加「输出」区（启动 / 用户脚本 print / 报错都在这里）、
    没有断点时明确提示「会直接跑完」、**文件有未保存改动时拒绝调试**
    （否则断点行号会和磁盘版本错位 ✗）、Windows 断点路径统一小写；
  - REPL：首次执行先回一句「正在启动解释器，首次约 1~3 秒…」，
    执行放**后台线程**（不卡行情 / 界面）；
  - 「对比 ▾」以前只在**有未保存改动**时才显示 → 现在**有文件就显示**。
### desk：编辑器第三轮（v1.3.7-3）

- **断点红点回归修复**：路径小写只用于断点表 key，查 tab 仍用原始路径。
- **终端对齐 VS Code**：ANSI 16 色渲染、切换 Shell（cmd / PowerShell / bash）、
  跟随输出（往上翻暂停）、500 行缓冲、历史 ↑↓、清屏 / 中断 / 重开 / 系统终端。
- **删除「对比」功能**（用户：没什么用处）：前端 MergeView + 后端
  `editor_diff` / `_git_head_text` 全部移除。
- **AI 助手 = pi-web 桥**（`minibt/desk/ai.py` 重写）：启动 pi-web（终端里跑
  配置的命令 + `/` 就绪探测）、`POST /api/agent/new` / `/api/agent/<id>`
  注入 prompt、`?session=<id>&sidebar=collapsed` iframe 只显示对话窗口；
  命令 `ai_open` / `ai_prompt` / `ai_context` / `ai_service_start|stop|status`
  （全部后台线程）。设置项 `ai_service_url` / `ai_service_command` /
  `ai_service_cwd`；旧 `ai_chat` + `ai_api_key` 已删除。
- **前提体检**：`ai.node_info()` 查 `node`/`npx` + 版本（≥22.19）；
  `_ai_ensure_service()` 在启动前先判，没装 Node 就给「装 Node + 网址」的
  可执行提示（不再等 30 秒报「没就绪」）。
- **新增测试** `tests/test_minibt_desk_ai_piweb.py`（11 个用例，用**假 pi-web**
  验证协议：probe / 新会话 / 续会话 / 上下文拼装 / URL 深链 / 前端入口）。

### desk：AI 助手（v1.3.7-4，零 npm）

- **移除 pi-web 桥**：`minibt/desk/ai.py`、`ai_service_*` 设置、网页页签 iframe
  全部删除 → **AI 功能不再需要 Node / npm** ✓
- **内置 AI 助手**：`minibt/desk/agent.py`（会话存储 + OpenAI 兼容流式 +
  工具循环）+ `jslib/src/desk/ai-page.ts`（会话列表 + 多开对话标签）。
  - 会话存 `~/.minibt/ai/sessions/*.json`（标题 / cwd / 消息，最多 400 条）；
  - 工具：`list_dir` / `read_file` / `grep` / `write_file` / `run_command`，
    沙箱在会话工作区内（越界拒绝、写 ≤200KB、命令 ≤25s）；
  - 命令：`ai_sessions` / `ai_new_session` / `ai_history` / `ai_send` /
    `ai_stop` / `ai_rename` / `ai_delete` / `ai_context` / `ai_status` /
    `ai_insert_code` / `log_tail`；
  - 设置：`ai_base_url` / `ai_model` / `ai_api_key` / `ai_tools` / `ai_max_turns`；
  - 前端：左栏会话（搜索 / 右键重命名删除）、顶部多开标签、流式消息、
    工具调用块、代码块一键插入编辑器、Ctrl+N / Ctrl+Enter。
- **新增测试** `tests/test_minibt_desk_ai_agent.py`（12 个用例，用**假 OpenAI**
  验证：会话 CRUD / 标题自动生成 / 工具沙箱 / 流式 + 工具循环 / 无 Key 提示 /
  取消 / 上下文注入 / 前端入口 + 「零 npm」断言）。

### desk：AI 助手（v1.3.7-5，成本 + 分支）

- **成本 / 上下文用量**：`agent.cost_of()` / `estimate_tokens()` /
  `messages_tokens()` / `MODEL_PRICES` / `MODEL_WINDOWS`；
  `chat_once()` 带 `stream_options.include_usage`（服务不认就自动重试），
  `AgentRun.track_usage()` 累计每个会话的 prompt/completion/total/cost/calls，
  并推 `ai_event:usage`（含 `context` / `window` / `percent`）。
  设置新增 `ai_price_in` / `ai_price_out` / `ai_context_window`（留空用内置表）。
- **会话分支**：`agent.branch_session(id, upto)` + `ai_branch` 命令；
  复制到指定消息、丢弃悬空 tool 消息、不继承 usage；前端消息右键
  「从这里分支（新会话）」/「复制这条」。
- **新增用例**（`tests/test_minibt_desk_ai_agent.py` 扩到 17 个）：
  usage 解析与累计、成本 / token 估算、分支截断与悬空 tool 清理、
  `ai_branch` 命令、前端用量与分支菜单断言。

### desk：紧急修复（v1.3.7-6）

- **资源管理器卡在「正在读取目录…」**：`app.ts` 的 `switch` 里编辑器/资源管理器
  的 `case` 标签被 AI 分支吞掉（`explorer` / `editor_file` / `debug_state` …
  全落进 `ai_sessions` 分支被丢弃）。现已重新挂回，并加源码级回归测试
  `test_app_switch_routes_each_patch_to_its_own_branch`（13 个标签齐全 +
  AI 分支不含编辑器标签 + 每个 case 只出现一次）。

### desk：AI 设置（v1.3.7-7）

- **输入被冲掉**：`SettingsPage.setValues()` 在用户正编辑输入框时**不重画**
  （`pendingRepaint` + `repaint()`），输入框提交打 `data-dirty`；避免「写完不显示」。
- **独立分区**：设置左侧新增「AI 助手」（`_renderAi`），UI 上不再埋进「个性化」。
- **`ai_ping` 测试连接**：`agent.ping()` 发一次 `max_tokens: 1` 请求，
  返回 `{ok, model, ms, error}`；前端 `setPing()` 把结果写在设置页 + toast。
- 新增 4 个用例（分区 / 不重画 / 保存生效 + ping 成功 / ping 失败）。

### desk：AI 设置不丢（v1.3.7-8）

- 前端 AI 设置**输入即写 `localStorage('desk.ai.*')`**，渲染时
  `后端值 || 本地缓存`；`_textInput(..., storeKey)` 支持该兜底。
- `app.ts::send()` 对 `ai_*` 命令自动附 `config: _aiOverride()`
  （settingsValues + localStorage）。
- 后端 `_ai_config(payload)` 支持 `payload.config` 覆盖（空值不覆盖），
  `ai_send` / `ai_regenerate` / `ai_ping` 全部传 payload。
- 新增 4 个用例（含「完全不落盘、只靠 payload.config 跑通一次对话」）。

### desk：PI 助手（v1.3.7-9，零 npm）

- 新模块 `minibt/desk/pi.py`：会话（含**导入 `~/.pi/agent/sessions/**.jsonl`**）、
  `models.json`（供应商 + Key + 模型 + 当前选择）、技能（`SKILL.md` 扫描 /
  启用开关 / **HTTP 搜 skills.sh + `git clone` 安装** / 本地目录安装 / 删除）。
- 命令：`pi_sessions|pi_new_session|pi_history|pi_send|pi_stop|pi_rename|
  pi_delete|pi_import|pi_models|pi_models_save|pi_skills|pi_skills_search|
  pi_skills_install|pi_skills_toggle|pi_skills_remove`。
- `agent.py` 扩展：会话级 `effort` / `permission`（工具白名单）/ `compress`
  （模型摘要压缩）/ `skillsPrompt` + system 提示；`event_type` 支持 `pi_event`；
  `save_session` 加锁 + 重试；`AgentRun.run` 异常也推 error。
- 前端：`pi-panel.ts`（会话列表）/ `pi-chat.ts`（对话页）/ `pi-models.ts` /
  `pi-skills.ts` / `pi-util.ts`；`editor-panel` 增加 PI 按钮（在「打开」左边）、
  左栏切换、`pi:<id>` 会话标签；删除 `ai-page.ts` 与设置页 AI 分区。
- 新增测试 `tests/test_minibt_desk_pi.py`（13 个用例）：供应商目录 / models.json
  往返 / 无 Key 不回退 Ollama / 技能安装(本地) + 启用 + 删除 + 越界拒绝 /
  skills.sh 离线降级 / pi JSONL 导入（含 toolCall/toolResult）+ 去重 /
  `pi_send` 流式 + 选项落盘 + 只读模式只给 3 个工具 / 无模型时明确报错。

### desk：PI 细节（v1.3.7-10）

- **PI 按钮激活态改用中性高亮**（不再用主题色），并删除误伤「保存」按钮的
  通用 `.desk-editor-btn.on` 主题色覆盖。
- **模型对话框兜底**：前端内置 `PI_PROVIDERS`（12 个供应商）+ 缓存最近一次
  `pi_models` / `pi_skills` 补丁 + 1.5s 超时提示「后端没有响应」；
  新增后端 `pi_status`（版本 / 命令清单 / 会话与模型文件路径）。
- **新建会话**：1.5s 没回包给提示；`piOnPatch` 加 try/catch（异常弹 toast）。
- 新增用例：`pi_status`、供应商兜底 + `setOffline` + 缓存、按钮配色断言。

### desk：模型保存（v1.3.7-11）

- 前端 `pi-models.ts` 新增 `readFields()`：保存 Key / 断开连接 / 保存前先把
  输入框的值写回 `data`（不再用渲染快照覆盖，修复「只有 apiKey 存上」✗）；
  勾选「设为当前」时模型名从当前输入取。
- 后端 `pi.provider_catalog()`：有保存值就只用保存值，不再拼内置模型列表。
- 新增 2 个用例（保存往返 + 前端 readFields 断言）。

### desk：模型选择（v1.3.7-12）

- `_pi_models_data()` 的 `active` 改为**已解析**（provider / model / base / keySet）。
- `pi.model_config()`：所选模型不在供应商列表内 → 退回第一个。
- 模型对话框：新增「对话将使用：<model>」、「测试连接」（走 `ai_ping`）、
  `/anthropic` 端点提示；`EditorPanel.piPingResult()` 把结果送回对话框。
- 新增 3 个用例。

### desk：会话列表（v1.3.7-13）

- 会话项改成 pi-agent-web 样式：标题行 + 悬浮按钮（当前会话 2 个：
  重命名 / 删除；其它会话 3 个：合并摘要 / 重命名 / 删除），CSS 默认隐藏、
  `:hover` 才显示；图标用 `ICON_MERGE` / `ICON_PENCIL` / `ICON_TRASH`。
- 新命令 `pi_merge`：`pi.merge_into()` 生成会话摘要（标题 / 时间 / 条数 +
  最近 12 条），追加成一条 `user` 消息到当前会话，源会话不动。
- 右键菜单保留并新增「合并摘要到当前会话」。
- 新增 3 个用例。

### desk：会话目录切换 / 分屏（v1.3.7-14）

- 新增 `Desk._apply_explorer_root(path)`：统一设置根目录 + 记
  `settings.explorer_recent`（最多 10 条，去重）+ 推
  `explorer` / `pi_sessions`(dir/default/recent) / `explorer_root` 三个补丁；
  `explorer_pick` / `explorer_system_dir` / `explorer_set_root` 全部改走它。
- `pi-panel.ts`：目录按钮 + 下拉菜单（默认目录 / 最近打开 / 选择文件夹）；
  会话按 `cwd` 过滤当前目录；`setDefaultDir` / `setRecent` / `onDir` / `onPickDir`。
- `editor-panel.ts`：新增 `paneSession[0/1]`、`_paneHost()`、`_targetPane()`；
  会话可在右栏打开（先分屏再点会话）、关分屏搬回左栏、关标签清理归属。
- 新增 5 个用例：切目录三个补丁 + dir/最近去重上限 + 不存在目录不动 +
  前端目录菜单/过滤断言 + 会话分屏结构断言。

### desk：PI 乱码 / 完全访问（v1.3.7-15）

- `agent.decode_bytes()`（UTF-8 → GBK → GB18030 → latin-1）+ `read_text_smart()`；
  `run_command` 改二进制捕获 + `stdin=DEVNULL` + `PYTHONIOENCODING=utf-8`；
  `read_file` / `grep` / `read_refs` 全部智能解码；`grep` 跳过
  `__pycache__` 等目录与二进制文件（`SKIP_DIRS`）。
- `terminal.py` 改二进制读 + 智能解码（cmd 的 GBK 中文不再花屏）。
- 权限默认 **`full`（完全访问，不询问）**：`TOOL_GROUPS['full']` = 全部 5 个工具；
  `pi_new_session` / `pi_send` 都 `setdefault('permission', 'full')`；
  前端 chip 文案「完全访问（不询问）」。
- 新增 6 个用例。

### desk：PI 停止原因可视化（v1.3.7-16）

- `MAX_TURNS` 6 → **12**（`settings.ai_max_turns` 可设 1~24）；到上限、
  `finish_reason=length`、空回复三种情况都会追加一条**可见** assistant 提示，
  不再只推 `done` 导致界面空白 ✗。
- `tool_result` 带 `elapsed`，对话页工具卡标题显示 `· 1.2s`。
- system 提示里写明「可以连续调用多个工具（最多 12 轮）」。
- 新增 4 个用例。

### desk：模型对话框「高级」限制（v1.3.7-17）

- `models.json` 新增 `limits`（`turns` / `timeout` / `output` / `read` / `window`），
  `pi.limits_of()` 带钳制，`model_config()` 合并进 agent 配置。
- `agent.run_tool(..., limits)`：命令超时、输出截断、单文件读取上限按设置走；
  `AgentRun` 把 `config` 里的限制传给每次工具调用。
- 前端 `pi-models.ts` 底部「高级」条（4 个下拉）+ CSS；
  `pi_models` 补丁带 `limits`，保存后立即生效。
- 新增 4 个用例。

### desk：混合编码（v1.3.7-18）

- `agent.decode_bytes()` 改为**按行解码** + `_decode_one()` 多候选
  （UTF-8 / GBK / GB18030 / Big5）+ 「GBK→UTF-8」二次解码修复，
  用典型乱码字符打分挑最优 → 同一条命令里 UTF-8 与 GBK 混排也能各解各的。
- `run_command` / `read_file` / `grep` / `@文件` / 终端面板全部受益。
- 新增 3 个用例（混合字节 / 乱码修复 / 混合脚本输出）。

### desk：PI 未安装检测（v1.3.7-19）

- `pi.install_status()`：`which('pi')` + `pi --version`（10s、`stdin=DEVNULL`），
  30 秒缓存，返回 `{installed, command, version, hint}`。
- `pi_status` 带 `installed` / `piCommand` / `piVersion` / `hint`。
- 编辑器 PI 按钮未安装时 `disabled` + 安装提示 tooltip；
  首次显示即查 `pi_status`；点击被拦下并 toast。
- `_apply_explorer_root()` 未安装时不再同步 `pi_sessions`。
- 新增 6 个用例。

### desk：PI 对话页（v1.3.7-20）

- 思考：`_post_stream` 收 `reasoning_content`/`reasoning`/`thinking` → `thinking` 事件；
  会话里保存 `thinking`，`api_messages()` 发送前剥离（不算上下文）。
- 每轮用量 `usage_of()`（含 cached：OpenAI/DeepSeek/Anthropic 三种写法），
  `track_usage()` 返回单轮并推 `round`；tool 消息保存 `args`/`elapsed`。
- `_ai_session_payload` 保留 tool 行 + `thinking`/`usage`/`model`/`seconds`
  （修「重开会话只剩一排 deepseek-flash」）。
- 前端 `pi-chat.ts` 重写：思考/工具折叠卡、每轮用量 + 复制、代码块复制、
  右侧节点导航（点击跳转 + 滚动高亮）、右键粘贴、流式 token/t-s 徽章、
  回到底部按钮、markdown 列表修复。
- 新增 5 个用例。

### desk：PI 对话页三处细节（v1.3.7-21）

- 代码块底色：`pre code` 重置为透明（行内 `code` 的底色不再串到代码块）。
- 结论下方始终有「复制」按钮（`desk-pi-copy-answer`），不再依赖 usage 是否存在。
- 右键粘贴改走后端：`pi_paste` 命令（`QApplication.clipboard()` → tkinter 兜底），
  前端 `applyPaste()` 插到右键时的光标处。
- 新增 4 个用例。

### desk：终端 / REPL（v1.3.7-22）

- `repl.py`：`from minibt import *` 的名字逐个搬进 `exec` 的 namespace
  （另加 `np`/`pd`）；启动横幅 `@@banner@@`/`@@ready@@` 不混进命令输出。
- 终端 / REPL 面板可拖动高度（顶部 5px 拖拽条，默认 220px，上限 75vh）。
- 删除「AI 对话」按钮；关闭「×」移到最右。
- 终端提示符跟随 `cd`（显示当前目录最后一段，title 为完整路径）。
- 新增 4 个用例。

### desk：终端合并 + 发给 AI（v1.3.7-23）

- 工具栏「终端」「REPL」合成一个按钮：打开上次用的页签，右键可选页签。
- 「发给 AI」改为二级菜单：选中代码 / 整个文件 / 文件地址 → 选会话 → 插入输入框；
  编辑器右键、资源管理器右键（文件地址 / 全部代码）同样支持。
- 会话目标含「＋ 新建会话」；未打开的文件先 `editor_open` 读回来再发；
  PI 页签在前台时退回上一个打开的文件。
- `PiChat.appendToInput()` 追加并聚焦，状态栏提示「按 Enter 发送」。
- 新增 3 个用例。

### desk：PI 操控 desk（v1.3.7-24，MCP 方案 M1）

- 新增 `minibt/desk/tools.py`：`SPECS`（9 个 `desk_*` 工具）+ `call()` 白名单分发 +
  `audit()` 审计（参数脱敏）。
- `agent.TOOLS` 合并这些定义；`TOOL_GROUPS` 新增 `desk` 档（`default` 不含）；
  `run_tool(..., desk=…)` 路由，`AgentRun` 传 desk 句柄与会话 id。
- 前端权限 chip 多一档「操控 desk（会点按钮）」。
- 新增 `tests/test_minibt_desk_tools.py`（13 个用例）。
- 方案文档：`13.29_pi_mcp_desk_control.md`（已加 mkdocs 目录，标注 M1 完成）。

### desk：PI 操控 desk（v1.3.7-25，MCP 方案 M2）

- 新增 8 个 `desk_*` 工具：`desk_open_page` / `desk_backtest_run` /
  `desk_optimize_run` / `desk_strategy_status` / `desk_positions` / `desk_orders` /
  `desk_order` / `desk_strategy_live`（共 17 个）。
- `confirm` 闸门：`desk_order` 与 `desk_strategy_live(start)` 缺 `confirm` 不执行，
  返回 `need_confirm` + 中文说明（模型反问用户），并写审计。
- 下单只允许限价单（`price > 0`），`local=true` 走本地模拟；
  回测/优化通过 `queue_ui` + `_on_strategy_start` 触发。
- 新增 7 个用例（共 20 个）；方案文档 13.29 标注 M2 完成。

### desk：PI 操控 desk（v1.3.7-26，MCP 方案 M3）

- 设置键 `ai_desk_allow`（默认开）/ `ai_desk_order`（默认关），已加入
  `user_prefs.SETTING_KEYS`；`tools.flags()` 读取并做闸门
  （只读工具与「停止策略实盘」不受总开关限制）。
- 审计：`tools.recent_audit()` / `clear_audit()`；命令
  `ai_desk_settings` / `ai_desk_save` / `ai_audit` / `ai_audit_clear`；
  设置页「PI 操控 desk」区块（两个开关 + 查看/清空 + 日志区）。
- 新增 6 个用例（共 26 个）。

### desk：MCP 服务端（v1.3.7-27，MCP 方案 M4）

- 新增 `minibt/desk/mcp.py`：stdio JSON-RPC 2.0（initialize / ping /
  tools/list / tools/call），工具表复用 `tools.SPECS`，执行复用 `tools.call`。
- CLI：`--config`（写 `~/.minibt/ai/mcp.json`，合并已有 server）、
  `--embedded`（离屏 desk）、`--list`（打印工具表）。
- 新增 `tests/test_minibt_desk_mcp.py`（10 个用例）。
- 方案文档 13.29 标注 M4 完成，M5（反向 MCP / 运行中实例桥接）为下一步。

### desk：本机桥 + 反向 MCP（v1.3.7-28，MCP 方案 M5）

- `bridge.py`：127.0.0.1 + 一次性 token 的 HTTP 桥（`/health` `/tools` `/call`），
  信息写 `~/.minibt/ai/bridge.json`；Desk 启动自动开、退出关闭；
  `mcp.py` 默认优先转发到运行中的 desk。
- `mcp_client.py`：读 `mcp.json` 的外部 server（懒启动 + 60s 缓存），
  注册成 `mcp__<server>__<tool>`，`run_tool` 路由；`ai_mcp_tools` 可关。
- 设置页新增「MCP 本机桥」「接入外部 MCP 工具」两个开关。
- 新增 7 个用例（共 17 个）+ `tests/fake_mcp_server.py`。

### desk：反馈批量修复（v1.3.7-29）

- 复制走 `clipboard_set`（后端系统剪贴板）。
- `desk_add_indicator` / `desk_remove_indicator` / `desk_clear_indicators` 支持 `page`，
  默认用当前活动本地页；新增 `desk_local_pages`、`desk_clear_indicators`、
  `desk_clear_drawings`（工具共 20 个）。
- `Bt._load_strategies` 直接读源码 exec，修「改了策略还是跑旧代码」。
- `PiChat.scrollToBottom()` + 切页调用；PI / 终端 / REPL 输入框支持 ↑↓ 历史。
- 新增 `local_switch`（本地图表 CSV → CSV），前端本地图表改用它。
- `pi_send` 执行中排队 + `queued` 提示，`AgentRun` 结束自动放行。
- 新增 9 个用例。

### desk：命令矩阵 + 3 处反馈（v1.3.7-30）

- 新增 `scripts/desk_tool_matrix.py` + 文档 `13.30_desk_command_tool_matrix.md`
  （243 条命令 × 20 个工具的覆盖表）；`tests/test_minibt_desk_tool_matrix.py`
  强制文档与代码同步。
- 本地图表 / 实时图表工具栏新增「更多指标」按钮。
- PI 输入框多行也强制 ↑↓ 翻历史。
- 执行中插话改为**追加到本轮**（`AgentRun.append_user` / `_drain_pending`），
  不再 stop+重启；失败才退回排队。

### desk：A 批工具（v1.3.7-31）

- 新增 12 个工具：`desk_set_cycle` / `desk_open_chart` / `desk_close_chart` /
  `desk_replay` / `desk_indicator_picker` / `desk_templates` /
  `desk_apply_template` / `desk_save_template` / `desk_layouts` /
  `desk_layout_apply` / `desk_editor_add_indicator` / `desk_book_watch`（共 32 个）。
- 对照表重新生成：已覆盖 25 条命令；新增 5 个用例。

### desk：B 批工具（v1.3.7-32）

- 新增 13 个工具：`desk_editor_open` / `desk_editor_save` / `desk_editor_new` /
  `desk_editor_delete` / `desk_editor_check` / `desk_explorer_set_root` /
  `desk_explorer_system_dir` / `desk_explorer_op` / `desk_strategy_manage` /
  `desk_strategy_switch` / `desk_strategy_remove` / `desk_repl_eval` /
  `desk_terminal_run`（共 45 个）。
- 保存 / 删除 / 新建 / 资源管理器新建都**回读校验**（不再假成功）。
- 对照表重新生成（覆盖 35 条命令）；新增 6 个用例。

### desk：C 批工具（v1.3.7-33）

- 新增 13 个工具：布局保存/删除/收藏、`tv_list`/`detail`/`source`/`star`/`live`/
  `script`/`reload`、`desk_replay_trade`、`desk_screenshot`（共 57 个）。
- 截图：工具 → `ui_action{screenshot}` → 前端页截图 → 后端落盘 → 工具返回路径（带超时）。
- `_json()` 改为合法截断（不再把 JSON 截成半截）；`file:` 策略源码直接读文件。
- 对照表重新生成（覆盖 43 条命令）；新增 5 个用例。

### desk：D 批工具（v1.3.7-34）

- 新增 12 个工具：`desk_login_futures` / `desk_login_stock` / `desk_account_kind` /
  `desk_close_charts` / `desk_theme` / `desk_position_action` / `desk_order_action` /
  `desk_ticket_order` / `desk_alerts` / `desk_add_alert` / `desk_drop_alert` /
  `desk_layouts_export`（共 69 个）。
- 交易类（平仓 / 撤单 / 买卖盘下单）进 `DANGEROUS`，必须 `confirm`；
  登录缺凭证返回 `need_user_input`（模型反问用户）。
- 对照表重新生成（覆盖 54 条命令）；新增 5 个用例。

### desk：E 批工具（v1.3.7-35）

- 新增 `desk_close_tabs`（页面 / 编辑器页签 / PI 会话，全部或指定）与
  `desk_open_ui`（日志 / 设置 / 命令面板 / 首页 / 报价 / 工作台 / 研究 / 登录）；
  `desk_open_page` 的 kind 扩展 home/quote/settings/logs/palette（共 71 个工具）。
- 前端：`ui_action` 新增 `close_tabs` / `open_ui`；`EditorPanel.closeTabs()`。
- `desk_open_page` 非法 kind 改为 JSON 错误；新增 3 个用例。

### desk：F 批工具（v1.3.7-36）

- 新增 15 个工具：数据平台（list / query / preview / quality）、
  运维（tokens / token_issue / tasks / task_run / task_toggle）、
  研究（list / start / cancel）、工作台（snapshot / limits）（共 85 个）。
- 这些走模块 API（同步返回数据），对照表加 `MANUAL_COVERS` 正确标注覆盖。
- 新增 3 个用例；对照表：85 个工具 / 覆盖 72 条命令。

### desk：文档（v1.3.7-37）

- 新增使用手册 `manual/13.29_pi_mcp_usage.md`（MCP 介绍 / 三种用法 / 权限 / 速查 / 排错）。
- 方案稿移到 `minibt_desk/13.29_pi_mcp_desk_control.md`，mkdocs 两条目录分别指向。
- 测试：`test_docs_have_plan_and_usage` 校验文档位置与关键内容。

### desk：PI 独立界面（v1.3.7-38）

- 新增 `PiPage`（编辑器 `variant:'pi'`）+ `PiWelcome` 初始化页：
  首页「预警中心」下面 / 顶栏「＋ → PI 助手」两个入口（去掉「零 npm 依赖」字样）。
- 隐藏 8 个桌面专属按钮与右键「加到图表」（只隐藏，功能保留）；左栏固定 PI 会话；
  初始化页不是页签，发送即新建会话；新会话先显示初始化样式；关完页签回到初始化页。
- `app.ts` 补丁路由改用 `_editorPanels()`（覆盖 PI 独立界面）。
- 新增 `tests/test_minibt_desk_pi_page.py`（7 个用例）；手册 13.29 补一节。

### desk：PI 独立界面增强（v1.3.7-39）

- 初始化页「最近会话」（5 条，置顶带 📌，点一下打开）。
- 新设置键 `pi_root`（PI 页独立目录）/ `pi_pins`（置顶）；命令 `pi_pin`；
  目录类命令带 `pi:true` 时只改 PI 的根。
- 侧栏会话置顶（☆/★ + 右键），后端置顶优先排序。
- 初始化页发送带 `title`（首句 40 字）→ 新会话立刻有名字。
- 拖入文本可用；拖文件 / 粘图片给出明确提示（WebEngine 拿不到路径）。
- 新增 5 个用例（共 12 个）；对照表 244 条命令。

### desk：AI 悬浮对话窗（v1.3.7-40）

- 新增 `pi-float.ts`：紧凑对话（发到会话，非一次性问答）+ 输入框/发送/模型 chip，
  底部「执行中才出现」的不定进度条。
- 贴主窗口四边 <28px 自动收起成小圆标，点图标恢复；位置/收起边持久化。
- 激活条件：pi 已安装 + 模型已配置；入口＝＋菜单「AI 悬浮窗」+ `Ctrl/⌘+Alt+A`。
- 修：`app.ts` 漏路由 `pi_status`（PI 按钮未安装禁用此前未生效）。
- 新增 6 个用例。

### desk：悬浮窗增强（v1.3.7-41）

- `@文件` 联想（`ai_files`）+ 拖文本；标题栏「会话 ▾」切换最近 12 个会话；
  贴边展开后鼠标离开 900ms 自动收起，📍/📌 钉住可关闭（持久化）。
- 修：`app.ts` 漏路由 `ai_files`（PI 会话 / 编辑器的 @文件此前不生效）。
- 新增 3 个用例（共 9 个）。

### desk：浮窗独立窗口 + 会话搜索（v1.3.7-42）

- 新增 `minibt/desk/float_window.py` + `pi_detach_float`：第二个 Qt 置顶窗口，
  加载 `desk.html?pi=float`（前端只渲染悬浮窗），共用同一个 Desk / 桥，补丁广播。
- PiFloat 标题栏新增 ⧉「浮到窗口外」；会话下拉加搜索框（即时过滤）。
- 无 Qt 窗口（浏览器 / 测试）时只提示不崩；退出时关闭浮窗。
- 新增 4 个用例（共 13 个）；对照表 245 条命令。

### desk：PI 页会话 + 本地布局修复（v1.3.7-43）

- 修：PI 独立页的 `onCommand` 覆盖了 `payload.id`（会话 id）→ 会话删不掉 /
  打不开 / 页签变「PI」；现在原样透传 payload。
- `openPiSession()` 新建页签先用 `piRows` 已知标题。
- 新增 `local_layout` 命令 + `desk_set_layout{local,symbols,page}`：
  本地图表按数据集逐格装布局（先推 layout 再逐格 local_load）。
- 新增 4 个用例；对照表 246 条命令。

### desk：MCP 可用性优化（v1.3.7-44）

- 新增 `desk_find_indicator`、`desk_sequence`（一次调用多步，≤6，禁危险工具）；
  `desk_add_indicator` 自动解析别名 + `need_key_choice` 候选 + `next_hint`。
- `desk_replay` 支持本地图表（`ui_action: replay`）；本地加指标/回放自动取当前数据集。
- `desk_status` 增加 `hints` / `local_pages`；`indicator_picker` 描述澄清「不添加」。
- 新增 5 个用例；对照表 87 工具 / 246 命令；手册补 3.6。

### desk：系统提示 + 工具合并（v1.3.7-45）

- `AgentRun.with_system()` 新增「工具选择规则」（先 find / sequence 多步 / 本地带 local /
  picker 不添加 / 先 status），并给一个完整示例。
- 布局 6 个工具合并为 `desk_layouts{action}`（list/apply/save/delete/favorite/export），
  工具总数 87 → 82；对照表 MANUAL_COVERS 同步（覆盖 74 条命令）。
- 新增 3 个用例（共 61 个）。

### desk：工具合并 + sequence 引用（v1.3.7-46）

- tv(7) / datahub(4) / ops(5) 合并为 `desk_tv` / `desk_datahub` / `desk_ops`{action}；
  工具总数 87 → 69，对照表覆盖 78 条命令。
- `desk_sequence` 支持 `$0.resolved` 依赖引用（嵌套 / 列表下标），查→加一步完成。
- 新增 3 个用例（共 64 个）；手册 13.29 更新。

### desk：再合并 5 组 + sequence 提示（v1.3.7-47）

- `desk_local` / `desk_account` / `desk_research` / `desk_book` / `desk_drawings`
  改为 action 单入口，工具总数 69 → 62；对照表覆盖 82 条命令。
- `desk_sequence` 每步回执新增 `hint`（下一步推荐工具）。
- 新增 2 个用例（共 66 个）；手册 13.29 更新。

### docs：changelog v1.3.7 段整理（按主题分组）

- `minibt_docs/docs/changelog.md` 的 `[v1.3.7]` 段重排：导语改写成四段主线，
  新增「阶段地图 / 关键数字 / 升级注意 / 收尾状态」四张表；
  56 轮迭代降为 `####`，按 A~H 八组（崩溃与指标目录 / 编辑器 /
  AI 设置与 PI 对话 / MCP 工具桥 / 文档矩阵 / 独立界面与浮窗 /
  让模型更快选对工具 / 账户·图表·悬浮窗收尾）归位，正文内容未删改；
  「本版收尾状态」提升为同级小节，关键数字同步到最新（1743 passed /
  `desk.js?v=mw9h3gyb`）。
- mkdocs 每页目录（`toc_depth: 3`）仍只列版本 + 分组，不会冗长。

### desk：悬浮窗附件位置 + 窄窗口自适应（v1.3.7-57）

- 悬浮窗 📎 挪到底部模型按钮左边（22×22，同高）；输入行只留输入框 + 发送。
- 根因修：flex 链缺 `min-width: 0` → 页宽 1179px（窗口 1028px）把工具栏右侧 /
  对话导航 / 发送按钮 / 状态栏挤出屏幕。
  `.desk-editor*` / `.desk-pi-*` 全链路收缩；工具栏窄窗口换行；状态栏正文改 span
  省略号；LSP 徽标短标签（完整说明进 tooltip）；初始化页与宿主互斥。
- 实测 1200~760 宽 0 横向溢出，760 宽 17 个工具栏按钮全部可见。
- 新增 `tests/test_minibt_desk_pi_layout_fit.py`（6 项）；全量 1763 passed。

### desk：行情数据工具 + 图表缩放 + 预警条件（v1.3.7-58）

- 新增 `desk_market`（klines / indicator / summary / quote）：直接给模型
  OHLCV 数字、指标序列、报价 + 统计，不再靠截图做像素解析；本地 CSV 用
  `local:true`。
- 新增 `desk_bars{action:"all"|"last", count}`：等价图表右键「全部K线 /
  最新K线（300 根）」（视图缩放，走前端回执 `bars`）。
- `desk_drawings` 加 `action:"toolbox"`：等价右键「画线」（左侧工具箱开关）。
- 预警标签改成「预警 上穿 12680」（带穿过 / 上穿 / 下穿）。
- 系统提示新增第 9、10 条（数据优先、别改 `chart_data_length`）。
- 工具 62 → 64；新增 `tests/test_minibt_desk_market_tools.py`（15 项）。

### desk：分析工具 P0/P1/P2 + 终端条 + PI 首页（v1.3.7-59）

- `desk_market` 新增 levels（前高低 / 斐波那契 / POC-VAH-VAL）、stats（ATR/RSI/
  分位/趋势）、patterns（K 线形态）、depth（五档压力）、digest（紧凑文本）。
- 新增 `desk_scan`（多合约指标筛，≤30 个）与 `desk_strategy_data`
  （回测收益/回撤/逐笔/净值/买卖信号）；三者都是只读工具。
- 终端页签条：清屏…系统终端整组贴右、紧挨 ×（关闭按钮不再抢 auto 边距）。
- PI 首页：关掉全部页签后显示初始化页（含「有页签但未激活」自愈）；
  首页发送改成 `pi_send{id:""}`，后端先建会话（标题=首句）再跑模型，删掉
  兜底定时器（以前会重复建两个会话）。
- 工具 64 → 66；新增用例至 21 项；全量 1784 passed。

### desk：右键入口 + PI 首页 + F1（v1.3.7-60）

- 图表右键（实时 / 本地）补 4 个工具栏入口：更多指标、模板、策略管理、保存当前布局。
- PI 首页：模型 chip 显示真实选中模型（`pi_models.active`）；`pi` 版本改用
  `pi --version`（1.5.1），不再复用 minibt 版本号；最近会话只列 3 个、点击打开。
- AI 悬浮窗快捷键 `Ctrl+Alt+A` → **F1**（微信截图占用了前者）。
- 全量 1788 passed；构建 `desk.js?v=mwa1zcqu`。

### desk：`desk_market{action:"analysis"}` 一次拿全套（v1.3.7-61）

- 新增 analysis：一次取 K 线 → levels + stats + patterns + 紧凑 text（+ 图上指标），
  3 轮往返降到 1 轮，实测 0.087s / 回执约 2.6KB。
- 系统提示推荐先 analysis，再按需下钻；手册 13.29 同步。
- 新增 1 个用例；全量 1789 passed；构建 `desk.js?v=mwa2gogw`。

### desk：资讯 / 财经日历 P0（v1.3.7-62）

- 新增 `minibt/desk/info/`（providers / cache / service）：AkShare 适配
  （限速 + 重试 + 主备接口）、SQLite 缓存（TTL）、缓存优先 + 后台抓取。
- 首页「事件日历」改用真实财经日历（`news_economic_baidu`，按天传 date），
  抓完推 `info_calendar` 局部刷新，取不到回退静态。
- 新页面「资讯中心」：快讯（60s 自动刷新）/ 要闻 / 日历 + 搜索 + 数据源徽标 +
  右键「让 AI 分析这条」；设置页新增「资讯数据源」。
- MCP：`desk_news` / `desk_calendar`（只读）；`pip install "minibt[news]"`
  可选依赖；工具 66 → 68。
- 新增 `tests/test_minibt_desk_info.py`（13 项）；全量 1801 passed。

### desk：资讯 P1（宏观 / 合约资料 / 标的资讯页）（v1.3.7-63）

- 数据层：宏观 6 序列、合约规则、库存、基差（快照缓存 12h/12h/6h/1h，失败只降级一块）。
- 资讯中心加「宏观」「期货」两个 tab；新增**标的资讯页**（图表右键「资讯 / 财务…」，
  顶部 pill 在多布局多个合约间切换）。
- `info_macro` / `info_symbol` 改后台线程（实测同步会卡 3 秒）。
- MCP 新增 `desk_macro` / `desk_fundamentals`（只读），工具 68 → 70。
- 新增 `tests/test_minibt_desk_info_p1.py`（11 项）；全量 1813 passed。

### desk：资讯 P2（富途优先 + 财务/公告 + FTS5 + 事件标记）（v1.3.7-64）

- 新增 `info/futu_source.py`：个股**快照 / PE·PB / 资金流**优先走富途 OpenD
  （复用 desk 已连的 StockApi），没连富途自动降级 AkShare 并在回执里注明。
- 财务摘要（AkShare，缓存 24h）/ 公告（30min）/ 资金流（5min）按接口成本排 TTL；
  东财 `…` / `--` 占位值当空串。
- 资讯缓存加 **FTS5 trigram** 全文搜索（<3 字自动 LIKE）。
- 图表 **K 线事件标记**：财经日历中/高重要性事件按天打点（<0.2 秒，失败不影响行情）。
- 资讯中心「AI 摘要」：当前 15 条交给 PI 总结（先建会话再问）。
- 新增 `tests/test_minibt_desk_info_p2.py`（13 项）；全量 1826 passed。

### desk：用户四条反馈修复（v1.3.7-65）

- 标的资讯页：关掉标签后再打开打不开（closeTab 没清缓存引用）→ 修。
- 设置「资讯数据源」删掉 Tushare 提示。
- 悬浮球：设置里可选背景色（`pi_float_color`，持久化 + 恢复默认），
  小球文字改「π」并放大到 22px。
- K 线事件圆点：改用 LWC v5 的 `createSeriesMarkers`；本地图表 bars 回退；
  历史区间无交集时标在最后一根；日历推给所有图表页。
- 新增 `tests/test_minibt_desk_v137_fixes3.py`（4 项）；全量 1830 passed。

### desk：事件圆点贴顶 / 标的事件 / π 主题色 / 会话去重（v1.3.7-66）

- 图上事件圆点改为**顶部 DOM 徽标**（缩放也贴顶、无文字、tooltip 看内容），
  只画**与标的有关**的事件（股票公告 / 期货品种相关日历），宏观不上图。
- 新增「事件圆点：全部事件都画」开关（`chart_events_all`，默认只中/高重要性）。
- 悬浮球 π 的字色回到主题色（去掉自选底色的深色覆盖）。
- 新增 `agent.cleanup_sessions` + 命令 `pi_cleanup` + 设置按钮「清理重复会话」。
- 补回每格周期链路 / `_isTradeCell` / `local_switch` / 本地预警 `account: 'local'`。
- 全量 1832 passed；构建 `desk.js?v=mwa90lcx`。

### desk：标的资讯页改金融小插件 + 事件卡片 + 多账户策略 + 开图不阻塞（v1.3.7-67）

- 标的资讯页改用 `pylightcharts` 插件：Company Profile（QuoteHeader+TextBlock）/
  Fundamental Data（DataGrid，缺失填 `-`）/ Technical Analysis / Top Stories。
- 后端 `_symbol_widgets()` 一次给全 quote / profile_text / fundamentals /
  technical（`ta_summary`）/ stories。
- 事件圆点按天分组 + 悬停弹出「当日事件」卡片（.desk-cal-pop）。
- 多账户加策略：按图表页账户 key 取实例（`account_key_for` +
  `_fallback_trade_account`），不再报「需要指定账户实例 account」。
- 开图先出 K 线：辅助命令延后（`_deferCommands`）；股票跳过天勤合约校验。
- 新增 `tests/test_minibt_desk_v137_fixes4.py`（8 项）；全量 1840 passed。

### desk：资讯页跟随主题 + 控件 + 关页加固（v1.3.7-68）

- 标的资讯页：`applyTheme()` 别名 + 固定主题调色板（浅色下文字不再发灰）；
  Fundamental Data 数值列加宽 + 报告期下拉；Technical Analysis 周期下拉；
  Top Stories 搜索框（`info_news{query}`）。
- 事件圆点旧 `title` 关闭（只保留悬停卡片）。
- `info_symbol_events` 改后台线程（实测阻塞 4 秒）；切页 / 关页容错，
  图表页关不掉 / 空白页遮挡修复。
- 新增 5 个用例；全量 1845 passed。

### desk：资讯页浅色主题 / 小数 / 表格高度 / Top Stories（v1.3.7-69）

- Fundamental Data：浅色主题补全表头 / 悬停 / 斑马线颜色；按行数撑高度不出滚动条。
- Company Profile：开 / 高 / 低 / 昨收保留 2 位小数；成交量 / 持仓量用整数
  （`QuoteHeader` 新增 `intFields`）。
- Top Stories：资讯缓存为空时就地抓一次（后台等待），公告 + 资讯都显示。
- 新增 2 个用例；全量 1847 passed；构建 `desk.js?v=mwabml3q`。

### desk：资讯多源合并 + 去重 + 关键词 + 宏观加速（v1.3.7-70）

- `fetch_market_news()`：财新 + 同花顺合并去重（去 `【标签】`、补 url、按时间排序）。
- `fetch_symbol_news()`：个股 / 期货 = 专属源 + 全市场关键词匹配（名称、代码、
  品种、`沪X`）+ 新浪快讯；统一去重。
- 标的资讯 / 资讯中心「期货」tab 都接这套（新增「相关资讯」区块）。
- 宏观：先推缓存、仅过期或手动刷新才抓；前端按 key 合并补丁。
- 新增 3 个用例；全量 1849 passed；构建 `desk.js?v=mwacporj`。

### desk：资讯联动 / 自选筛选 / 摘要缓存 / F10（v1.3.7-71）

- 图表页 `focusTime()`：点资讯跳到对应 K 线 + 4 秒高亮徽标；`news_focus` 纯前端。
- `info_related`（自选 + 打开图表 + 持仓的合约与名称）+ 资讯中心「只看自选/持仓」。
- `ai_summary`：按天缓存到 `~/.minibt/ai/summary.json`，同一天命中缓存不重跑；
  Shift 点强制重生成。
- `F10` = 当前图表的标的资讯（右键菜单文案同步）。
- 标的资讯页小插件标题中文化：标的概况 / 基本面数据 / 技术分析 / 最新资讯。
- 新增 `tests/test_minibt_desk_v137_fixes5.py`（5 项）；全量 1855 passed。

### desk：资讯右键菜单 + 标的识别（v1.3.7-72）

- 资讯交互：左键不动作；右键菜单（打开原文 / 打开图表 / 复制 / 让 AI 分析）；
  双击打开原文；NewsFeed 面板支持 onItemContextMenu / onItemDoubleClick。
- 标的识别 `_symbolOf`：自带 symbol → 自选/持仓名称 → 文本里的期货/股票代码；
  认不到时菜单显示「找不到标的」并明确 toast，不再静默。
- `news_focus`：带 symbol 时先 `openChart` 真打开，再等 K 线到位后跳时间 + 高亮。
- 新增 `tests/test_minibt_desk_v137_fixes6.py`（4 项）；全量 1859 passed。

### minibt：信号（signals）+ 技术分析模板（v1.3.7-73）

- 新增 `minibt/signals.py`：`Threshold`（原 Osc）/ `Compare`（原 Trend）/
  `Custom`，1 多 · 0 中立 · -1 空；`minibt.utils` / `minibt` 顶层可导入。
- `@tobtind(signals={...})` 挂到结果上，`IndicatorsBase.signal_of()/signal_map()`；
  目录新增 `has_signal` / `signal_spec`（`CATALOG_SCHEMA 9`），内置信号用
  `BUILTIN_SIGNALS` 注册表覆盖 RSI/CCI/ADX/MACD/MA 等。
- `pylightcharts` 技术分析输出 `groups`（震荡 / 趋势 / 其他），面板渲染信号文案。
- `minibt/desk/ta.py`：`options / template / save_template / reset_template / snapshot`；
  标的资讯页技术分析「⚙ 设置」对话框（勾选指标 + 阈值/比较 + 保存模板/恢复默认）。
- 新增 MCP `desk_ta`（options / snapshot / set / reset），工具 70 → 71。
- 新增 `tests/test_minibt_signals_ta.py`（12 项）；全量 1901 passed。

### desk：信号接通圆点 / 预警 + 多模板 + TA 列对齐（v1.3.7-74 ~ -75）

- `ta_signals`：技术分析信号 → 图表最后一根 K 线旁的徽标（悬停看明细，10s 节流）。
- 信号预警：`kind:"signal"` + `key` + `op`，15s 缓存、触发日志明确；预警对话框
  新增「类型：价格 / 指标信号」；MCP `desk_add_alert` 支持信号。
- 多命名模板：`ta_templates` + `ta_template_name`，`desk_ta` 增 templates/use/save/delete，
  对话框底部模板下拉 + 另存为。
- 技术分析三列改 grid 固定列宽（中间数值列居中，不再对不齐）。
- 新增 4 个用例；全量 1905 passed；构建 `desk.js?v=mwanmdp7`。

### desk：AkShare 噪声静音 + 资讯自动认标的（v1.3.7-76）

- `providers._call()` 内静音 `PerformanceWarning` / `FutureWarning`，`TQDM_DISABLE=1`，
  日志不再被 pandas 碎片化警告与进度条刷屏。
- 资讯推送前 `_annotate_news_symbols()`：用**全市场名称索引**（3 字以上，最长优先）
  与合约 / 股票代码识别标的，条目自带 `symbol` —— 右键「打开图表」不再依赖
  「自选 / 已打开图表」，没开个股图表也能跳。
- `fetch_profile` 加巨潮 `stock_profile_cninfo` 备用（AkShare 1.18.64 的
  `stock_individual_info_em` 已抛 Length mismatch）。
- 新增 `tests/test_minibt_desk_v137_fixes7.py`（13 个用例）；全量 1917 passed。

### desk：工具栏「＋」更多指标和策略（v1.3.7-77）

- 实时图表 / 本地图表工具栏在「指标」右边新增 **`＋`** 快捷按钮，
  tooltip「更多指标和策略」，点一下直接开 `pylightcharts` 指标 / 策略选择器
  （`indicator_picker`，带当前 cell / 合约），少一层菜单。
- 新样式 `.desk-tool-add`（24px 窄按钮）；策略模式下随「指标」一起隐藏。
- 新增 2 个用例；全量 1920 passed；构建 `desk.js?v=mwaoq37w`。

### desk：「指标」菜单末两项只在实时图表（v1.3.7-78）

- 排查：实时图表 11 项（含「个人指标策略管理…」「策略管理…」），本地图表 9 项（本来就没有）。
- 给本地图表加过的两项**已回退**；用例锁定该现状（本地图表断言不含）。
- 构建 `desk.js?v=mwap0mua`。

### desk：定时任务（调度器 v2，v1.3.7-79）

- `ops.TaskScheduler` 升级：触发 `interval / daily(HH:MM, mon-fri) / manual`，
  动作 `builtin / tool（MCP 工具）/ ai（提示词）`，落盘
  `~/.minibt/desk/ops/scheduler.json`（任务 + 200 条历史）。
- 保护：skip_if_running、连续失败 3 次自动停用、每天次数上限、只在交易时段、
  跳过手工休市日（`holidays.json`）、异步执行不卡 tick；AI 任务默认只读权限，
  危险工具默认拒绝（勾选后才带 confirm，审计 `scheduler-confirm`）。
- `OpsService` 新增 `_run_tool / _run_ai / submit_due / run_task`；
  `_suite_tick` 改为异步提交，结果经 `on_result` 推 `ops_tasks` / `ops_task_output`。
- 运维页「定时任务」：工具下拉（71 项）/ 参数 JSON / 提示词 / 触发 / 保护开关 /
  列表（动作·触发·下次·状态）/ 立即跑·编辑·启停·删除 / 执行历史 / 手工休市日；
  设置页新增「启用定时任务」总开关（`scheduler_enabled`）。
- `desk_ops` 扩到 tasks / task_add / task_update / task_remove / task_history /
  task_run / task_toggle / holidays（仍 71 个工具）。
- 新文档 `minibt_docs/docs/minibt_desk/manual/13.32_scheduler.md`；
  新增 18 个用例；全量 1939 passed。

### desk：定时任务 P2（多步 / 条件 / 模板 / 导入导出，v1.3.7-80）

- `action.kind = "sequence"`：多步串联，支持 `$0.xxx` 引用、遇错即停、
  `continue_on_error`、非 JSON 结果按失败处理。
- `when` 前置条件：`{tool, path, op, cmp, value}`，支持
  `> >= < <= == != contains / truthy / falsy / count`；字符串不做大小比较，
  判断异常不拦任务。
- 模板库 6 个（开盘前简报 / 收盘复盘 / 资讯刷新 / 持仓风险巡检 / 每日清理 /
  行情快照落库）+ `add_from_template`；`export_tasks` / `import_tasks`。
- 运维页：动作下拉加「多步串联」（步骤 JSON）、前置条件框、模板下拉、
  导出/导入按钮；列表加「前置条件」列。
- `desk_ops` 增 task_templates / task_from_template / tasks_export / tasks_import。
- 用例 18 → 27；全量 1948 passed；构建 `desk.js?v=mwbdlhlb`。

### desk：定时任务 P3（失败推送 / 重试 / 停机补跑，v1.3.7-81）

- 任务级 `notify`：`error`（默认）/ `always` / `never`，走告警通道推企业微信 / 邮件，
  内容是「任务名 + 耗时 + 摘要 / 错误 / 跳过原因」。
- `guard.retries`（0~5）：失败重试，间隔 0.5s→1s→1.5s；只有最终失败才计 `errors`。
- `guard.catch_up`：停机期间错过的那一次开机补跑，仅限 6 小时内。
- 运维页表单 + 列表悬停提示；`desk_ops` 的 task_add / task_update 接受这三个字段。
- 用例 27 → 35；全量 1956 passed；构建 `desk.js?v=mwbdztkx`。

### desk：任务 DAG + 命令全量接工具（v1.3.7-82）

- 定时任务支持前置任务：`trigger.kind="after"`（上游成功后点名跑，`next_run=-1`
  表示等待）+ `guard.depends_on`（定时任务要求依赖最近成功，默认 24h）；
  环检测拒绝 A→B→A；`dependency_state()` 给界面 / PI。
- 新增 `desk_cmd{cmd, args}`（71→72 个工具）：白名单直通界面命令，走
  `desk.handle()` 同一条路径；`CMD_BLOCK`（36 条：动钱 / 执行代码 / 改权限 /
  删数据）拒绝并提示用专用工具；拼错给 `did_you_mean`。
- 命令矩阵：新增 `🔒 只走专用工具` 状态，统计「覆盖 / 🔒 / 内部 / 待补」，
  待补 173 → 0；文档 13.30 自动重生成，13.29 / 13.32 补说明。
- 新增 14 个用例；全量 1970 passed。

### desk：四个扩展页入口开放（v1.3.7-83）

- `＋ 新建 ▾` 恢复：交易工作台 / 策略研究 / 本地数据平台 / 平台·运维（4 项）。
- 命令面板恢复 7 条（4 页 + 工作台对账 / 导出审计 CSV），关键字补中文。
- `desk_open_ui` 白名单加 workbench / datahub / ops / info，前端 `open_ui` 分支补齐。
- 文档 13.17：入口全部开放 + 运维章节按**定时任务 v2**（触发/动作/when/DAG/
  重试/补跑/推送/模板/导入导出/休市日）重写；入口速查加 MCP 工具列。
- 新增 7 个用例；全量 1977 passed；构建 `desk.js?v=mwbfc0jy`。

### desk：告警通道加微信公众号推送（xtuis，v1.3.7-84）

- `ops.Notifier` 通道 2 → 4：`wecom` / **`xtuis`（公众号）** / `email` / `webhook`（通用）。
- xtuis：`GET https://wx.xtuis.cn/{token}.send?text=&desp=`（**`wx.` 前缀**），标题 200 / 正文 1000 截断；返回 HTML 视为失败（防止假成功）；
  可换自定 URL（`{token}` 占位）；缺 token 明确报错。
- 通用 webhook：GET/POST + 模板 `{title} {text} {level}`（Server酱 / PushPlus / 钉钉）。
- 运维页告警通道：新增公众号 token / 地址、自定义 webhook 地址 / 方法 / 模板；
  保存时四个通道各存一次。
- `desk_ops` 增 `notify_config` / `notify_test`；命令矩阵覆盖 222 / 🔒 35 / 待补 0。
- 新增 14 个用例；全量 1990 passed；构建 `desk.js?v=mwbin4jk`。

### desk：公众号推送域名修正（v1.3.7-85）

- 默认推送地址 `xtuis.cn` → **`wx.xtuis.cn`**（前者是官网首页，HTTP 200 但收不到）。
- xtuis 返回值是 HTML 时判为失败并提示正确域名，杜绝"看着成功其实没送到"。
- 运维页占位提示与文档同步；新增 1 个用例（共 14 个）。

### desk：定时任务界面 —— 参数骨架 / 说明 / 帮助面板（v1.3.7-86）

- 选 MCP 工具 → 参数框自动填骨架：`{"tool":名称,"args":{全部参数}}`，
  有默认填默认（`tools.UI_DEFAULTS` 22 组），没有用 `""`；后端接受整段动作 JSON。
- 参数框下方显示工具说明（作用 + 每参数 类型/必填/默认）+ 内置任务说明
  （`ops.BUILTIN_DOCS` 5 条：做什么 / 什么时候用 / 参数）。
- 新增「帮助 ?」面板：列出 72 个 MCP 工具（说明 + 参数 + 可复制骨架）与 5 个
  内置任务，带搜索；目录走新命令 `ops_catalog`（缓存，只推一次）。
- 新增 9 个用例；全量 2000 passed；构建 `desk.js?v=mwbjg8jm`。

### desk：定时任务三处修正（v1.3.7-87）

- 任务表状态列只放短标签（长原因进 title）+ `.desk-suite-table-wrap`
  （固定布局 / 省略号）→ 不再把页面撑出横向滚动。
- 定时 AI 任务改按 **PI 的 models.json** 解析模型与 Key（内置 AI 配置兜底，
  谁有 key 用谁），修掉「PI 能用、定时任务报没配 API Key」。
- 事件类型跟随配置（PI → `pi_event`），跑完刷新 PI 会话列表，`register(run)`
  支持 PI 停止；只读权限只作用于当轮，不写进会话。
- 新增 3 个用例（共 38 个）；全量 2003 passed；构建 `desk.js?v=mwbjuvgv`。

### desk：定时任务独立成页（v1.3.7-88）

- 新增 `SchedulePage`（tab `__schedule`）：原运维页「定时任务」卡片整体搬过来
  （表单 / 模板 / 导入导出 / 任务表 / 历史 / 休市日 / 帮助面板）。
- 入口：`＋ 新建 ▾ → 定时任务（工具 / AI / 内置）`、命令面板「定时任务」、
  `desk_open_ui{target:"schedule"}`。
- 补丁路由拆分：`ops_task*` / `ops_catalog` / `ops_holidays` → 定时任务页；
  `ops` / `ops_token` / `ops_notify` / `ops_versions` → 运维页。
- 新增 8 个用例；全量 2011 passed；构建 `desk.js?v=mwbka2yh`。

### desk：定时任务「工具」下拉为空（v1.3.7-89）

- 根因：拆页后只推 `tasks.snapshot()`（无工具清单），运维页以前靠 `ops` 补丁顺带获得。
- 新增 `OpsService.task_snapshot()` 统一带 `tools / builtins / enabled`，
  6 处推送全部替换；前端再加 `ops_catalog` 兜底。
- 新增 4 个用例（共 12 个）；全量 2015 passed；构建 `desk.js?v=mwbo48qc`。

### desk：命令行工具 `python -m minibt.desk.cli`（v1.3.7-90）

- 子命令：doctor / status / snapshot / tasks / run / history / rpc
  （`--payload` / `--file` / `--set k=v`，`--json` 出原始 JSON）。
- token 三种来源（env → --token → --token-file）；403 / 400 / 连不上都翻译成中文建议；
  `ops_task_*` 这类只推补丁的命令提示「已提交」。
- 新增 12 个用例；全量 2027 passed；文档 13.17 / 13.32 补用法。

### desk：告警通道搬到设置页（v1.3.7-91）

- 设置 → 系统设置 → **告警通道**（资讯数据源下方）：公众号 xtuis / 企业微信 /
  邮件 / 自定义 webhook + 发送测试 + 最近 8 条记录；填 token 保存即启用。
- 运维页的告警卡片移除（Token / 版本 / 状态保留），说明指向设置页。
- `ops` / `ops_notify` 补丁同时喂设置页；新增 5 个用例；全量 2032 passed；
  构建 `desk.js?v=mwbpkhz2`。

### desk：告警规则（v1.3.7-92）

- 新增 `ops.AlertRules`（`alerts.json`）：6 条规则（拒单 / 成交 / 预警 / 行情停更 /
  任务失败 / 后台异常），可配开关·等级·去重窗口；`notify_rule()` 统一发送 + 去重。
- 钩子：`trading.set_alert_hook`（拒单 / 成交）、`check_alerts`（预警）、
  `_watch_market_resume`（行情停更）、定时任务失败（task_error）。
- 设置页「告警通道」底部新增「告警规则」表（保存 / 恢复默认）；
  `desk_ops{action:"alert_rules"}` 支持 list / save / reset。
- 新增 11 个用例；全量 2043 passed；构建 `desk.js?v=mwbqgrkr`。

### desk：告警规则 P2（v1.3.7-93）

- 新增 3 条规则：`position_risk`（浮亏占市值 > 5%，可改）/`order_stale`
  （挂单超 10 分钟）/`login_lost`（交易连接从好变断）。
- 规则支持 `threshold` 阈值字段（带 label/unit），设置页多一个输入框；
  `trading.stale_seconds` 按规则注入（关掉=0）。
- 单测 11 → 17 个；全量 2049 passed；构建 `desk.js?v=mwbr09wx`。

### desk：告警 P3 + 四入口再收 + 说明上下布局（v1.3.7-94）

- 告警规则 9 → 14 条：`strategy_live` / `strategy_error` / `strategy_drawdown` /
  `news_macro` / `news_keyword`（后两条默认关）。
- 静默时段（默认关，23:00–08:00 只放严重）+ 每日汇总（默认关，16:00 一条）；
  `alerts.json` 存 `rules/quiet/digest`，PI 用 `alert_rules mode:"settings"`。
- 四个扩展入口（工作台 / 研究 / 数据平台 / 运维）再次注释关闭，**定时任务页保留**。
- 定时任务页工具说明改上下布局（整行独占 + 名字/说明/参数分行），帮助面板同步。
- 单测 17 → 29；全量 2063 passed；构建 `desk.js?v=mwbreszz`。

### desk：净值曲线 + 资讯关键词（v1.3.7-95）

- 新增 `ops.EquityStore`（`equity.db`）：每 60s 采一条账户净值，保留 400 天；
  `stats()` 给峰值 / 回撤 / 最大回撤 / 当日盈亏 + 曲线点；`ops_equity` 命令。
- `strategy_drawdown` 改读净值序列（重启不丢峰值）；设置页画 canvas 曲线。
- 资讯关键词自定义（`alerts.json.keywords`）：不依赖自选/持仓，命中标题或摘要
  就推；同一条不重复、同词 10 分钟最多 3 条；PI 用 `alert_rules mode:"settings"`。
- 新增 14 个用例；全量 2076 passed；构建 `desk.js?v=mwbsb1ko`。

### desk：告警分组 + 回测/优化完成提醒（v1.3.7-96）

- 规则表按 `source` 分组（交易 / 预警 / 行情 / 定时任务 / 持仓 / 策略 / 资讯 / 系统），
  组标题带条数。
- 新增 2 条规则（**默认关**）：`backtest_done` 回测完成、`optimize_done` 参数优化完成；
  `strategy_lab` 三处状态切换挂 `_notify_done()` → `desk.notify_lab_done()`，
  出错走 `system_error`。
- 单测 29 → 35；全量 2082 passed；构建 `desk.js?v=mwbtn9ak`。

### desk：告警中心页（时间轴 + 搜索，v1.3.7-97）

- 新增 `ops.AlertLog`（`alerts_log.db`，保留 180 天）：每条命中（含静默压制）
  落库（时间/规则/等级/标题/正文/通道/成败）；命令 `ops_alert_log` /
  `ops_alert_log_clear`；快照带统计。
- 新增页面 `AlertLogPage`（`__alertlog`）：入口 `＋ 新建 ▾ → 告警中心` + 命令面板；
  按天分组的时间轴、搜索（标题/正文/规则）、等级与规则筛选、统计、加载更多、清空。
- `desk_ops{action:"alert_log"}`（query / level / rule / limit / mode=clear）。
- 新增 10 个用例；全量 2092 passed；构建 `desk.js?v=mwbu5r54`。

### desk：告警中心一键复现 + 柱状图（v1.3.7-98）

- `alerts` 表加 `symbol`（老库自动 ALTER）；`notify_rule(..., symbol=…)` 记录合约，
  页面点击行 / 「打开图表」按钮 → `openChart(symbol)`。
- `AlertLog.daily(14)` + 页面近 14 天柱状图（等级堆叠 + 条数 + 日期，悬停明细）；
  命令与工具都带 `daily`。
- 单测 10 → 16；全量 2098 passed；构建 `desk.js?v=mwbuf6w2`。

### desk：技术分析标签固定右上角 + 开关（v1.3.7-99）

- 徽标从「整页 element + 按最后一根 K 线定位」改为挂在**图表格子**里，
  CSS `right:12px/top:10px` → 永远在图表右上角。
- 新增设置 `ta_badge`（默认开）：关掉后不画；开关放在标的资讯 → 技术分析 ⚙
  对话框（模板下拉下方），`set_setting` 落盘。
- 新增 5 个用例；全量 2103 passed；构建 `desk.js?v=mwbusdl7`。

### desk：TA 徽标悬停改卡片（v1.3.7-100）

- 禁用原生 `title`，改为悬停弹出 `.desk-cal-pop` 风格卡片：
  头部（项数 / 多空中立 / 评分）+ 每行「指标名 ｜ 看多·数值·备注」（红/绿/灰），
  贴图表格子右边界并夹在格子内。
- 本地图表页同步修好（此前仍是「按最后一根 K 线 + top:28px + title」的老实现）。
- 单测 5 → 9；全量 2107 passed；构建 `desk.js?v=mwbvf5sv`。

### desk：修「跑测试把告警真推到微信」（v1.3.7-101）

- `tests/conftest.py` 整个会话把 `MINIBT_DESK_OPS_DIR` 指到临时目录（不碰用户 token）。
- `Notifier._muted()`：pytest + 用户家目录的真实配置 → 静音；新增
  `home_notify_path()`（不受 `MINIBT_DESK_OPS_DIR` 影响）。
- `MINIBT_DESK_NO_NOTIFY=1` 可全局关推送（记录照样写，通道显示 local）。
- 新增 4 个用例；全量 2111 passed。

### desk：告警只认即时事件（v1.3.7-102）

- 资讯类：首扫只做基线（缓存里的旧新闻/旧日历不推）；日历缓存 `stale` 直接跳过。
- 回撤/持仓风险：必须有**本次运行**的采样，且只在「刚破阈值」推一次（回落才重置）。
- 策略启停：关窗口的 `stop_strategy_live()` 静默；内部重启不推；只有用户操作才推。
- 规则默认值不变（`strategy_live` 仍开）。
- 新增 9 个用例；全量 2120 passed。

### desk：PI 技能对话框搜索按钮竖排（v1.3.7-103）

- `.desk-pi-btn` 加 `white-space: nowrap / flex: 0 0 auto / min-width: 56px`，
  搜索行输入框 `flex: 1 1 auto; min-width: 0` → 按钮文字一行 ✓
- 小体验：空关键词给提示并聚焦；搜索中按钮变「搜索中…」+ 禁用（12 秒兜底复原）；
  未安装技能的空态文案更可操作。
- 新增 6 个用例；全量 2126 passed。

### desk：TA 首帧报错 + 技能搜索 404（v1.3.7-104）

- TA：K 线不足时 `note` 显示「数据不足」（异常原文进 `row.error`），
  `snapshot()` 用 `retry: true` 让前端 8 秒后自动再算一次；catalog 失败日志去重。
- 技能搜索：skills.sh 接口 `/api/skills` → **`/api/search`**，按新返回结构
  （`id/source/skillId/name/installs`）映射，安装包名取 `owner/repo`。
- 新增 7 个用例；全量 2133 passed。

### desk：PI 对话 / 悬浮窗 Markdown 表格（v1.3.7-105）

- `pi-chat.ts` 抽出并导出 `markdownToHtml` 等一套 Markdown 渲染（含 GFM 表格：
  对齐 / 补列 / 单元格行内格式 / XSS 转义）。
- 悬浮窗 assistant 气泡改用 Markdown（以前纯 textContent，表格只显示一堆 `|`）。
- 新增 `.desk-pi-table*` / `.desk-pi-float-bubble.md` 样式；8 个 vitest 用例，
  vitest 146 passed。

### desk：PI 圆点导航悬停两条提示（v1.3.7-106）

- 圆点与导轨容器不再设原生 `title`（改 `aria-label`），只留自定义浮出 label；
- 新增 3 个用例；全量 2136 passed。

### desk：圆点导航提示内容太少（v1.3.7-107）

- 回答节点提示改成两行「问：…（前 90 字）／答：…（前 140 字）」，用户节点带「问：」；
  `aria-label` 同步带问 + 答。
- CSS 提示卡片放宽到 320px、允许多行（最多约 3 行）。
- 用例 3 → 5；全量 2138 passed；构建 `desk.js?v=mwby8s84`。

### desk：圆点导航提示被挤成竖排（v1.3.7-108）

- 根因：导轨 `.desk-pi-nav` 只有 26px 宽，label 是它的普通 flex 子项 → 逐字换行。
- 修法：label 绝对定位（贴圆点左侧）+ `width: max-content` +
  `max-width: min(340px, 62vw)`；实测宽 358px / 4 行、不超出窗口。
- 用例 5 → 7；全量 2140 passed；构建 `desk.js?v=mwbyhx3u`。

### desk：格 1 残留指标删不掉（v1.3.7-109）

- 后端 `indicator_payload` 增 `pending_keys`；前端 pending 时保留范围改成
  `items ∪ pending_keys`，多余序列当拍删除（不再"只加不删"留残留）。
- `IndicatorLayer.removeSource()` 先物理删注册表序列（pane / overlay / 图例），
  即使不在 items 里也能删掉。
- 后端删除匹配改 `_same_indicator_key()`：忽略大小写 + 忽略 `:线名` 后缀。
- 新增 6 个用例；全量 2146 passed。

### docs：手册补齐「资讯中心 + 标的资讯」（v1.3.7-110）

- 新增 `minibt_docs/docs/minibt_desk/manual/13.31_news_center.md`（11 节）：
  两页分工、AkShare 可选 / 富途优先 / TTL 表、资讯中心五分区与条目三操作、
  标的资讯页 4 个插件（含 `ta_badge` 开关）、图上事件圆点、告警联动
  （`news_macro` / `news_keyword` + 只认即时事件）、设置页、PI 工具表、
  9 条前端命令对照、7 条 FAQ、按轮次的版本记录。
- 导航：`13.31 资讯中心与标的资讯`（手册）在前，原设计稿改标 **13.31a**，两篇互链。
- `mkdocs build --strict` 0 警告。

### desk：换合约后旧合约的线留在图上（v1.3.7-111）

- 用户截图 `持仓线没清理干净.png`：清仓后旧合约（约 800）的线还在，切到新
  合约（约 9000）时价格轴被拉到 0~12000，K 线压成一条线 ✗；预警线 / 挂单线
  同样要查。
- 修法（不再只靠"补丁能对上页面"）：
  - **价格闸门**：`_priceBand()` 取当前格最后 300 根 K 线的价格带，
    `_priceFits()` 上下留 50%；持仓 / 挂单 / 预警**画之前**过闸，
    `pruneForeignLines()` 撤销已存在的不合格线；`setBars()` 里复查一次；
  - **合约闸门**：`setPosition / setOrders` 带补丁的 `symbol`，
    别的合约的补丁一律忽略；
  - **清理加固**：新增 `clearAllLines()`，`resetForSymbol()` 与
    `setSymbol()`（合约变化）都调用；本地图表同款 + 换 CSV 时清线；
  - **指标图层**：补丁 `symbol` 变化先清空所有序列；主图**叠加线**若没有任何
    点落在当前价格带里直接丢弃（策略停止线就是这一类）。
- 新增 6 个用例；全量 2154 passed；构建 `desk.js?v=d1d1b706`。

### docs / 打包：sdist 过期自查（v1.3.7-112）

- 用户追问「改了 pylightcharts 是不是要重打？minibt 真的不用重打吗？」——
  实测两处 sdist 已过期（`pylightcharts` 的 `docs/changelog.md`、
  本包的 `CHANGELOG.md`）：根因是 **`python -m build` 之后又改了会被 sdist
  收录的资料**（CHANGELOG / RELEASE_NOTES / README / RELEASING / docs / tests）。
- 新增 `scripts/check_dist_fresh.py`（仓库根 `scripts/`）：把 sdist 里每个文件
  与工作区**逐字节**比对（`PKG-INFO` / `*.egg-info` / `build/` 自动跳过），
  过期返回 1；`RELEASING.md` 第 5 步已补。
- 新增 `tests/test_check_dist_fresh.py` 5 个用例。
- 附注：`data/utils.py` 是 `python -m build` 现场按**包内基础数据**重生成的
  （只会出现 `aliased / l2609_60 / pp2609_60 / test`）；若中途跑过
  `LocalDatas.rewrite()`（非 base_only），先重新 build 再上传 ✓。

### 测试

- 新增 `tests/test_minibt_desk_v137_indicators_alerts.py`（19 个用例）：
  目录完整性、三库条目数对平、NON_KLINE 不入目录、缓存指纹 / 重建、
  预警账户归属、`account_scope` 还原、本地预警取价、前端 6 处断言。
- `tests/test_minibt_desk_lsp.py` 断言同步成 `_button('预览', ...)`。

## [1.3.6] - 2026-11-06

> **一句话**：v1.3.5 之后的一批 **desk** 大修（11-04 ~ 11-06，7 轮用户反馈 +
> 2 轮自查），重点在**账户 / 交易 / 登录 / 行情**：三个统一账户（快期模拟 /
> 富途模拟 / TqAccount）且**按页面 / 按格独立**；「富途模拟」改成**富途官方模拟盘**；
> 交易面板改「快期式」四按钮、**全部限价（对手价）**、锁仓按平今 / 平昨拆单；
> 登录信息（含密码）持久化到独立文件；股票行情泵补齐；修掉「开图 / 换合约卡
> 158 s / 188 s」的卡顿根因。
>
> 详细发布说明见 [`RELEASE_NOTES.md`](RELEASE_NOTES.md)；逐条改动见
> `minibt_docs/docs/changelog.md` 的 `## [v1.3.6] - 2026-11-06` 段；
> `pyproject.toml` / `__init__.py`（`__version__` + `版本信息`）/ `README.md`
> 徽章已同步为 **1.3.6**；wheel + sdist 输出到 `minibt/dist/`
> （1.3.5 归档在 `minibt/dist/archive-1.3.5/`）。

### desk：账户 / 交易

- **期货登录信息持久化**（用户名 / 记住密码 / 使用实盘账户 / 期货公司 /
  资金账号，**交易密码永不保存**）：登录信息改存**独立文件**
  `~/.minibt/desk_login.json`，并从旧的 `desk_user_prefs.json` 自动迁移；
  前端加 `loginCache`（打开即回填）、字段一变 400ms 防抖落盘 + 关窗前再存一次
  （不点「登录」也不会丢）。
- **账户按页面 / 按格独立**：`Desk._home_key`（首页）+ `_account_keys`
  （`chart:SYM` / `chart:SYM#cell`）；数据读取按 key 显式取
  （`AccountView.payload/summary/tables/is_real(..., key)`），首页与每个
  实时图表页互不影响；多布局每格可各用一个账户。
- **首次打开实时图表按格 1 合约选账户**：股票 → 富途模拟，
  期货 → 快期模拟（**即使登录了实盘也默认快期模拟**）；之后用户手选的账户保留。
- 品种校验：股票页只能用富途模拟、期货页只能用快期模拟 / TqAccount，
  不匹配时**明确提示 + 下拉框弹回**。
- 本地图表：隐藏切账户下拉框，只接本地模拟账户；`local_account` 补丁与真实
  账户补丁**双向隔离**。

### stock_api：富途账户

- **「富途模拟」= 富途官方模拟盘**：`trd_env='SIMULATE'` 时 desk 强制开启交易
  上下文（不涉及真钱），登录框「启用交易」默认勾选；持仓 / 权益 / 委托
  **优先读富途**（`position_list_query` / `accinfo_query`），不再用 minibt 的
  本地记账账户。
- 标签 / 实盘判定按 `_trd_env`：`股票模拟（富途）` / `股票实盘（富途）` /
  `股票本地模拟`；只有 `REAL` 才需要二次确认。
- CN / HK / US 是**独立模拟子账户** → `_ensure_market()` 按需切换交易上下文；
  日本个股 / ETF / REITs **无模拟盘** → 下单明确报错（仅日本期货支持模拟）。

### desk：行情 / 体验

- **股票行情泵**：`pump()` 遍历所有行情源（期货 + 股票），富途侧 `deadline`
  按"秒"传；股票 quote 补齐买一 / 卖一 / 开高低收 / 昨收；一字线自动用最新价撑开。
- 买卖盘每次打开图表**默认关闭**；价格框 ▲▼：空值 = 卖一 / 买一，
  否则 ± 一个**最小变动价位**。
- 交易账户面板在 `_chartPageFor()` 返回 null 时不再抛异常（卡片 / 持仓正常渲染）。

## [1.3.5] - 2026-10-31

> 沿用 1.3.4 的打包流程；`pyproject.toml` / `__init__.py`（`版本信息` +
> `__version__` + `__version_info__`）/ `README.md`（徽章 + 更新亮点）已同步为
> **1.3.5**。本版内容按主题归并（明细见 `minibt_docs/docs/changelog.md` 的
> v1.3.5 段）。

### 亮点

- **新增「指标和策略」页（仿 TradingView）**：114 个 TradingView 指标做成卡片库
  （分组 / 搜索 / 收藏 / 热门 / 每页 24 张 / 自动缩略图），支持**添加用户自己的
  指标和策略文件夹**并递归加载；点卡片 = **新开一个页签的完整本地图表**
  （底部编辑器自动打开、指标/策略自动画到图上）；卡片右键可「打开 / 在图表上
  使用（选哪个图表） / 重载图表」；页签右键「查看原始码（只读）」；
- **代码展示统一** `# coding: utf-8` + `from minibt import *`，策略依赖的指标类 /
  函数通过 AST 依赖闭包一起带上（`cci.py` → `CCIStrategy` + `CCI`），老脚本
  打开时自动重建；
- **参数优化大修**：目标 3 → **9 个**、帕累托前沿 1~3 轴（含三维 canvas，
  可拖动旋转 + 悬停 tooltip）、「优化设置」（method / n_jobs / n_trials /
  sampler / pruner）、参数网格编辑器；`values_0` 恒 0 / 目标行内列被丢弃 /
  单目标 X 轴 / trial 差 1 等一批问题修好；优化超 1 分钟会提醒改用信号参数优化；
- **回测结果页的「回撤」副图可关**：新增 `config.drawdown_plot`（默认 `False`）；
- **多合约回测的盈亏副图不再空白**（同一根 K 线多条腿成交 → 重复时间戳 →
  lightweight-charts 报 `Value is null`）；
- **浅色主题**：等待页底色 / 分隔线 / 回放视窗三处不再发黑或跑偏；
- **图表观感**：画线导航条（间距 0、直角、隐藏滚动条但能滚）、副图删除不再
  连带、`vbar_up_color` / `vbar_down_color` 真正生效（alpha 0~255 → 0~1）、
  策略里的柱体 / 蜡烛 / 色带 / 参考线 / 水印 / VP / 表格在 desk 也按样式出图；
- **编辑器**：jedi 的 sys.path 显式带源码仓库根、可手动指定 minibt 路径、
  任何打开过的文件都能保存、个人指标「加不上图」不再报成功；
- **稳定性**：关 desk 不再刷 `runJavaScript: disabled in Discarded state`；
  图表右键菜单（全部K线 / 最新K线 / 画线 / 清除画线 / 截图）+ 原生右键拦截，
  截图改为后端落盘 `~/.minibt/exports/`；后台任务改为**按线程**捕获 stdout。

### 新增

**指标和策略页**

- 卡片列表（分组 / 关键词 / 收藏 / 热门排序 / 每页 24 张）+ 自动缩略图（首批
  纯 SVG；用户自己的指标 / 策略也会生成，且**保留颜色 / 线宽 / 虚线 / 柱状配色 /
  信号箭头 / 参考线**）；
- 用户分组：「＋ 添加指标和策略」（选文件夹，递归扫描 `.py`，分组名 = 文件夹名，
  存 `~/.minibt/desk/tv_groups.json`）与「－ 删除指标和策略」（只删记录）；
  `TradingView` 是系统默认分组（不可删），「全部分组」= 默认 + 用户分组合并分页；
- 卡片右键菜单：`打开指标 / 打开策略`、`在图表上使用 ›`（只列本地 / 实时图表，
  菜单出现在鼠标处）、`重载图表`（单张重算，深浅两套封面）；
  「刷新」右边新增「重载图表」（整页 24 张，后台线程逐张推送）；
- 收藏：图表工具栏 ★ / 顶栏页签 ★ / 收藏 tab（跨分组，且只显示仍在分组里的）；
  图表工具栏「截图」= 保存 PNG **并且**覆盖卡片封面（按当前主题，深浅各一套）；
- 页面右下角「回到顶部」圆钮（能滚动且滚过筛选行才出现）；
  自动缩略图保留指标样式（线宽 / 点虚线 / 柱状涨跌配色 / 信号箭头 / 参考线）；
  卡片封面按主题分开（`<key>_light.png` / `<key>_dark.png`，不跨主题回退）；
- 页签：名称带「指标 / 策略」（`策略 · cci · CCIStrategy`）、同一个指标只开一次、
  页签条支持**滚轮横向滚动**、关页签跳「后一个 / 前一个」；
- 进图表时同步 `local_list`（商品搜索框和本地图表一样有内置 / 用户数据）；
  连了行情时商品搜索框可在线搜合约并替换本页数据（`tv_live`）。

**参数优化 / 回测**

- 9 个优化目标 + 每目标权重；帕累托前沿 1~3 轴（三维 canvas）；优化设置
  （method / n_jobs / n_trials / sampler / pruner）与参数网格编辑器；
  `OPTTargetType` 全量指标参与计算；单目标时 X = 账户权益、tooltip 用真 trial 序号；
  慢优化 1 分钟提醒改用「信号参数优化」；`config.drawdown_plot`。

**图表面板 / 画线 / 主题**

- 多布局画线共用左侧导航条（图标原大小、`title` 悬停、间距 0、直角、
  隐藏滚动条但可滚、按「合约|周期」持久化、作用于最后点击的格）；
- 加载策略后再加指标（策略线与指标线互不覆盖）、删副图不连带、浅色主题三处；
- 回测 / 参数优化页图表工具栏的「画线 / 删除画线」改图标；图表右键菜单五项。

**编辑器 / 脚本**

- jedi 显式 sys.path（源码仓库优先）+ 悬停 / 补全注释；设置里可手动指定
  minibt 路径（默认关，改完即时生效）；任意打开过的文件都能保存；
- 多策略文件弹窗选类；文件里「导入」的指标类也能加到图表；
- 生成的个人脚本头部统一、缺依赖自动自愈、参数个数按 AST 统计。

**界面 / 稳定性**

- 页签可滚轮横滚、关页签跳邻居；原生右键在顶栏 / 工具栏 / 画线导航条 /
  二级报价 / 指标和策略页禁用（输入框与编辑器保留）；
- 关窗 / 页面 discard 后不再 `runJavaScript`；后台任务按线程捕获输出、
  `FilteredOutputRedirector` 只在仍是自己的流时复原。

### 修复

**指标和策略页**

- 「在图表上使用」菜单跑左下角、列出指标图表页 → 用鼠标坐标 + 排除指标页；
- 用户策略卡片缩略图只有 K 线、点开不画策略 → 跑一遍策略（预览模式，秒级）；
  根因是 `_local_indicator_payload()` 的 `page` 只按 CSV 反查 → 补丁没 `page`；
- 启动时 `[desk-personal] 跳过 xxx.py：NameError` → 生成头部补依赖 / 老脚本自愈；
- 「全部分组」看不到 TradingView、系统默认分组被删 → 用真 key + 拒绝删除；
- 本地图表页被「挤爆」（底部面板要最大化才见 / 编辑器滚不动）→ 去掉多余的
  `position: relative`，恢复 `.desk-stack > *` 绝对铺满；面板回到 3:1；
- **截图后卡片「指标 / 策略」标记消失**：标记改成**前端 HTML 层**
  （`.desk-tv-card-tag`），SVG / PNG 封面都有；类型信息也写进缩略图页脚。
- **指标表格的定位**：表格挂在**图表区**（`.desk-cell-main` / `.desk-chart-host`）
  并给 `.desk-cell-main` 补 `position: relative`，拖动也限制在图表区内 →
  右侧二级报价出现时不再遮挡、也不会跑出图表。
- **表格 / VP 跟随的三条规则**：鼠标移动时显示历史那根；**停住 2 秒**自动回
  实时；在最新那根 / 右侧空白时始终用最新数据（以前"保留旧跟随"会卡顿）。
  只有 VP 没有表格的策略也起计时（以前直接 return，VP 永远停在历史）。
- **实时图表挂策略后 VP / 表格仍不跟随鼠标**：`crosshairBoundCells` 以前记
  布尔"已订阅"，而挂策略会**重建格子**（新 chart 实例）→ 再也不给新图表订阅
  十字线 → 只有实时更新。改成存**订阅的 chart 实例**，chart 一换就重新订阅。
- **实时图表的 VP / 表格不跟随鼠标**：十字线只有"离开绘图区"才回落最新
  （两根之间不再当成离开）；`VpOverlay._search()` 在数据范围内取**最近的
  一根**（不再只认精确命中）；新 K 线到达时先显示最新、鼠标再动才跟随。
- **「＋ → 实时图表」切合约**：`_renameChart()` 补 `setCellSymbol(0, …)`
  （交易标的 / 画线键跟着换）+ `tab.baseLabel`；`_on_switch_symbol()` 改用
  `data_length()` 取数并记 K 线状态（`_note_kline_state`），修掉"初次切合约
  只有 2 根 K 线、切周期才正常"。
- **实时图表的 VP 档区**：`realtime._vp_spec()` 以前把 `price_bars=None`
  原样传下去 → 用整段数据的 low/high（矩阵按 500 根分档）→ 分布被压扁；
  现在默认 500（显式 0 = 整段，语义不变）。表格后端共用、前端已改每格订阅。
- **编辑器切换标签时在资源管理器定位文件**：`revealInExplorer()` 逐级展开
  上层目录（懒加载回来继续）、`scrollIntoView` 滚进可见区并短暂高亮；
  面板刚建/刚换根目录时先记住，根目录到了再定位。
- **本地图表 VP（成交量分布）位置 / 表格跟随鼠标**：VP 的档区窗口以前用
  `price_bars or 120`（指标默认 500）→ 分布被压扁、挤在价格区间下半部分；
  现在按指标的 500 根窗口、逐行还原（`vpLo/vpHi` 长度 = 矩阵行数）。
  十字线改为**每格各自订阅**（以前只订阅格 1 → 其它格的表格 / VP 收不到
  十字线，看着像静态图）。
- 页签无滚轮滚动 / 关页签回首页 / 指标页重复打开 / 卡片封面跨主题 → 已修；
  本地图表编号改为「当前最小空闲序号」（关完再建回到 1，指标图表页不占号）；
  添加分组后立刻切到新分组 ✓

**参数优化 / 回测**

- 优化图表三张图空白、按当前目标重新优化失效、`values_0` 恒 0、单目标 X 轴与
  trial 差 1、多合约盈亏副图空白、drawdown 开关、慢优化提示。

**图表 / 画线 / 主题**

- 画线工具条间距 / 直角 / 滚动条；浅色主题分隔线、等待页、回放视窗；
  `vbar_*_color` alpha 口径；格 1 柱体配色；策略 vbar / 蜡烛 / 色带 / 参考线 /
  水印 / VP / 表格样式；`stop_price` 数值离谱；`IndFrame.linestyle` 与单线
  `BtIndicator.linestyle` 静默失效；`Ture` 笔误。

**编辑器 / 脚本**

- 悬停无注释、只能保存个人目录、个人指标假成功、多策略默认取第一个、
  导入指标类不被识别、`custom Stop` 子类失效 / 脚本函数被误当指标。

**稳定性**

- `runJavaScript: disabled in Discarded state`、图表右键菜单不自动收起、
  输出流串台 / `I/O operation on closed file`。

### 测试

- 新增/更新一批 desk 测试（画线、格策略指标、hist 主题、vbar 颜色、编辑器保存、
  止损线、浅色主题、副图删除、优化选项 / 目标 / 帕累托、LSP 路径、编辑器 minibt
  路径、本地图表保留指标、策略选择、慢优化提示、导入指标、右键菜单截图、
  指标和策略页 / 用户分组）与 `jslib/test/strategy-lab-optimize.test.ts`、
  `jslib/test/pareto-3d.test.ts`、`jslib/test/sub-pane-visibility.test.ts`。

### 依赖

- `pylightcharts>=0.1.8`（本版已随 0.1.8 打包：desk 前端资源
  `desk.js` / `desk.css` 与 `pylightcharts/headless.py` 的 `<body>` 主题、
  `abstract.py` 的柱体基线 `base`、`colors.normalize_color()` 都在该版本里）。

## [1.3.4] - 2026-10-30

### 亮点

- **`Gui.Desk` 进 Jupyter / Notebook**：notebook 里不再弹 Qt（那会卡死 kernel），
  自动改成**浏览器壳 + iframe** 内嵌；`tutorials/plots/12~15` 四个最小示例
  （btplot / 回测 / 回放 / 实时）随包提供；
- **本地图表多开 + 副本独立**：顶栏「＋ → 本地图表」/ 首页-图表工作台
  「新建本地图表」/ 命令面板都能新建副本（本地图表1 / 2 / 3…），
  指标 / 策略按**页面**存，同一份 CSV 开两页也互不影响；
- **一个页面只放一个策略**（换策略 = 先清上一个，布局 / 指标保留）；
  需要多策略时用**多开页面**、「策略实盘」（可同时多个子进程）或
  **只读叠加**（只画线、不交易）；
- **多布局真正可用**：格 2..N 的 K 线 / 指标增量更新、持仓线 / 挂单线按格
  路由、换合约只换鼠标最后点击的那一格；加载策略时「合约数 ≤ 现有格数」
  就**保持当前布局**（多余格不关），格数不足才自动加格；
- **计算搬到后台线程**：重策略（如 `KalmanFilterStrategy` 的 Python 循环）
  不再卡界面 —— 先推 K 线、后台算线、算完自动上图；收盘后自动挂起；
- **图表右键增强**：新「我的模板 ▸ / 保存当前指标模板」；画线共用左侧
  竖排导航条，按「合约|周期」本地持久化。

### 新增

- `Desk._strategy_lives`：**策略实盘支持多策略**（一个文件一个子进程），
  重复启动同一文件被拒；按钮显示 `运行中 ×N`，`停止实盘` = 停止并删除全部；
  「策略管理」里每行可改两个开关（新 K 线 next / 运行 next）/ 看 PID / 删除；
- **只读叠加（display-only strategy）**：`run_overlay(replay=False)` 只跑
  `__init__` 画线，**不跑 next、不碰账户**，同一页可叠多个；
  身份 =（文件绝对路径, 类名），同一个再点 = 重新加载；
  「🗑」菜单与「策略管理」里可单条删除，两个运行开关置灰；
- **本地图表多开**：独立页签 `local:1/2/3…`、页面级指标与策略、
  「复制当前页面」、页签显示当前策略名（`本地图表1 · test`）；
- **多布局画线**：左侧竖排导航条（46px，带 `趋势线 · TrendLine（Alt+T）`
  tooltip），存 `~/.minibt/desk/drawings.json`，键 = `合约|周期`；
- **图表右键「我的模板 / 保存当前指标模板」**（本地图表 + 实时图表，
  作用在鼠标最后点击的那一格）；
- **指标 / 策略后台计算**：`_strategy_results` 队列 + `_heavy_jobs` 门控
  （后台任务期间主线程不碰 tqsdk）、格 2..N 的完整库指标延后补推；
- 编辑器工具栏「策略管理」按钮（紧跟「加到图表」）、图表工作台两栏
  （左列本地图表 / 右列新建）、回放实验室「弹菜单选本地图表页」；
- `pylightcharts>=0.1.7`（desk 前端资源重建，见 pylightcharts CHANGELOG）。

### 变更

- **加载数据只加载 K 线**（本地图表）：重新打开本地数据不再带出上次的指标，
  指标请重新「加到图表」或用指标模板；
- **布局规则（加载策略后）**：格数 < 策略合约数的布局**禁用**；相等可切
  （合约按格对上）；更大可切（多出来的格子没有策略线、保留原样）；
- 命令面板快捷键 `Ctrl/⌘+K` → **`Ctrl/⌘+P`**（`Ctrl+K` 让给编辑器的注释）；
- 本地 / 实时布局按 `scope` 分开保存；保存同名布局需「确认替换」；
- 指标增量更新与 K 线一致（同根 1 点 / 新 K 线至少 2 点 / 断线按时间补缺口）；
- 编辑器「帮助」页补充：一个页面只支持一个策略、重载会先清理、
  指标失败不加载、`next()` 运行时出错不影响图表。

### 修复

- **指标缺口被连成直线**（`Chandelier_Exit` / `SuperTrend_STRATEGY` 等一半
  `up` 一半 `dn` 的指标）：首尾空点裁掉、中间缺口补透明点，效果与
  TradingView `plot.style_linebr` 一致；
- **`ADX_and_DI` 每次计算都刷 `RuntimeWarning`**（`invalid value in
  less_equal` / `divide`）：numpy 的 errstate 是**线程局部**的，desk 后台线程
  拿不到主线程的 `np.seterr` → 改为 `astype('float64') + fillna` 比较、
  除法包 `np.errstate`；
- **多布局**：第 2..N 格没有持仓线、切合约整页跳走、工具栏切布局后端不知道、
  指标总加到格 1、右键关闭格 2 关成格 1、切换主题其余格仍是深色；
- **策略线串格 / 策略管理删不掉**：`_local_indicator_payload()` 末尾又
  `strategy['items'] + items` 把全部线加一遍 → 只用本格那一组；
  策略管理按行 `key`（页签 id / 绝对路径|类名）删除，关页清理幽灵记录；
- **策略 `next()` 运行时报错不再影响图表**：首次弹窗、之后只写日志，
  图表 / 指标不动；指标算不出来时回滚 + 弹窗（不加载上图表）；
- **本地图表「初始加载」策略线串格**：后端推的布局不再用前端过期的每格
  合约回写；格 3 加第一个指标不显示（占位 K 线）→ 数据到了自动补推；
- **收盘后还在空转**：行情指纹没变直接 return，末根超过
  `max(10 分钟, 5 个周期)` 判定已收盘并挂起，日志只记一次；
- 首页下方预览图严格按「K线」开关显示（空数据自动重试，不再永远迷你折线）；
- `AdaptiveTrendTrail` 预热期 `RuntimeWarning`、`Twin_Range_Filter` 短数据
  越界、富途/天勤行情与订阅、主题与主副图分隔线等零星问题。

### 测试

- 新增 / 扩充 desk 回归：`test_minibt_desk_async.py`、
  `test_minibt_desk_cell_indicators.py`、`test_minibt_desk_local_pages.py`、
  `test_minibt_desk_layout_strategy.py`、`test_minibt_desk_overlay_page.py`、
  `test_minibt_desk_one_strategy.py`、`test_minibt_desk_runtime_errors.py`、
  `test_minibt_desk_cell_switch.py`、`test_minibt_desk_drawings.py`、
  `test_minibt_desk_context_templates.py`、`test_minibt_desk_home_preview_kline.py`
  等，以及指标和策略页 / VP 表格跟随 / 切合约相关的一批新测试
  （本机 `pytest -k desk` **1307 项通过**）；
- 前端 `jslib` 侧 `vitest` **132 项通过**，`tsc --noEmit` 干净。

### 依赖

- `pylightcharts>=0.1.8`（0.1.7 → 0.1.8：desk 前端资源重建 —— 指标和策略页、
  VP / 指标表格跟随鼠标、多布局十字线按格订阅、柱体基线 `base`、
  截图后端落盘、颜色 alpha 规范化等）。

> 1.3.4 的逐项记录（含每个 P 编号修复）见
> `minibt_docs/docs/changelog.md` 的 `[v1.3.4]` 一节。

## [1.3.3] - 2026-10-27

### 亮点

- **纯指标策略不再多出「回测结果 / 指标记录」两页**：没有 `next()`、
  不产生交易的指标策略（例如 `vp.py` 的 `RollingVolumeProfile` 系列）
  只画指标，不会因为“权益是一条恒定平线”被误判成有回测数据。
- **本地图表 / 实时图表策略链路**：本地 CSV 策略、配对策略、实时多合约策略
  的指标、信号、持仓线、停止线、回测结果和参数优化入口统一。
- **图表与指标样式**：`PlotInfo` 的线型、线宽、图例、`bandstyle`、
  `signalstyle`、`tablestyle`、水印、逐点信号文字等能力在 desk 中落地。
- **行情与账户**：期货 / 股票数据源分流、天勤与富途账户切换、模拟账户、
  持仓线、预警线、二级报价和多布局状态同步继续完善。
- **文档**：VS Code 扩展更新到 **minibt-charts 0.3.11**：新增 desk 终端入口、
  天勤密码加密存储、连接体检与离线演示；安装命令和解释器自动探测保持可用。

### Changed

- `pylightcharts` 继续作为图表渲染依赖，最低要求保持 `>=0.1.5`
  （推荐安装最新 0.1.6，包含 panels / desk 资源更新）。
- 纯指标策略的输出按“是否真正发生交易”判断，不再按权益曲线是否水平判断。

### Fixed

- 修复本地图表 / 实时图表切换合约后旧指标、旧策略线、旧预警线残留。
- 修复本地策略回放时停止线越界、持仓线与成交次数统计不一致。
- 修复部分策略回测结果页 / 交易记录页为空但仍生成页签的问题。
- 修复富途股票行情订阅、账户切换与下单数量单位相关问题。
- 修复图表主题、副图分隔线、图例齿轮、指标 NaN 断点等显示问题。
- 修复 RL 特征预处理对 pandas 只读数组赋值失败（`assignment destination is read-only`）。
- 修复 RL 推理回测中收益曲线与时间索引长度不一致（`Length mismatch`）。
- 新增 RL 样本外改造基础设施：`fit_range` 训练区间归一化、独立 `eval_env`、
  `train/splits.py` 时间切分 / walk-forward。
- 新增 `train/metrics.py`：从权益曲线 / 收益率计算净收益、Sharpe、Sortino、
  最大回撤、Calmar 等验证指标。
- 新增验证集评分回调 `eval_score(env)`：可按净 Sharpe / 回撤选择最佳 checkpoint，
  默认仍使用累计 reward。
- 新增 `train/walk_forward.py`：`make_folds` / `run_walk_forward` 回调式 walk-forward 执行器。
- 新增 `train/ensemble.py`（多 seed 编排 / 动作聚合）与 `Strategy.rl_reset_index()`
  （fixed / random / incremental 起点）。
- 新增 `run_walk_forward_ensemble` / `runs_to_frame`：walk-forward × 多 seed 高层编排
  与结果表。
- 新增 `summarize_runs` / `save_runs_csv`：按 seed 汇总 walk-forward 指标并导出 CSV。
- 新增 `tutorials/elegantrl/08_walk_forward.py`：train / val / test 独立环境的一折示例；
  支持 `--all-folds` + `--seeds` + CSV 汇总。
- 新增 `tutorials/elegantrl/09_rl_ensemble.py`：多 seed actor 集成推理，
  同时评估单 actor / ensemble / 最佳 seed。
- 09 支持 `--csv` / `--report` / `--html`，导出单 actor 评估结果。
- 新增 `train/report.py`：Markdown walk-forward 报告；08 支持 `--report`。
- 报告新增 `best_seed` / `save_walk_forward_html`；08 支持 `--html`。
- `08_walk_forward.py` 支持全 fold / 多 seed / CSV / Markdown 报告。
- 08 会按 `--metric` 自动输出最佳 run / 最佳模型目录。
- 新增 `best_model_config` / `save_best_model`；08 支持 `--deploy` 复制最佳 actor。
- 新增 `load_best_actor`：从 `config.json` 恢复 actor / 架构并 eval。
- 新增 `tutorials/elegantrl/10_deploy_inference.py`：从部署目录复现 test 推理。
- 新增 `tutorials/elegantrl/11_rl_experiment.py`：RlExperiment / Bt 门面示例。
- 新增 `train/reward.py`：手续费 / 滑点 / 换手 / 回撤惩罚，03/05/06 已接入。
- 新增 `train/state.py`：仓位 / 持仓天数 / 浮盈 / 回撤 4 维状态，03/05/06 已接入。
- 新增 `train/small.py`：小样本小网络 / 离散动作 / 随机起点默认参数。
- 指标绘图设置审计：修正 `overlay` 拼写、TuLip/FinTa/TqTa/TA-Lib/BtInd
  等主图指标的 `overlap`，并隐藏 `thermo_long/short`、`signals` 等交易信号线。
- 修复 desk 布局管理：本地 / 实时布局按 `scope` 分开，布局行只显示布局 /
  合约 / 周期；应用多格布局时显式带上 `count`，避免只恢复成单图。
- 保存布局增加同名确认：同名布局需再次点击「确认替换」才覆盖，
  同一作用域内布局名称保持唯一。
- 修复本地布局恢复指标：布局里保存的 `pta_sma:sma` / `tv:X:trend`
  线条 key 先还原成目录基础 key 再计算，指标不再闪一下被清空。
- 修复实时图表多布局指标总加到格 1：工具栏 / 收藏 / 右键 / 键盘精灵
  统一按 `activeCell` 发送 `cell`，右键也先激活鼠标所在格。
- 修复 `AdaptiveTrendTrail` 等 TradingView 指标在 NaN 预热期的
  `RuntimeWarning`，并检查其它指标无同类警告；`Twin_Range_Filter`
  短数据不再越界。
- 指标全量推送只在历史未变时 `update(last)`，避免实时色带整段重绘闪烁。
- 指标增量更新与 K 线一致：同根只推 1 点；新 K 线至少推最后 2 点；
  断线重连按周期 / 时间差补缺口，缺口过大再全量重算。
- 新增 `minibt/elegantrl/REFACTOR_DETAILS.md`：样本外改造逐项原理与代码说明。
- 新增 `best_actor_path` / `restore_best_actor`：训练结束自动把验证最优 actor 覆盖为 `act.pth`。
- `Strategy._get_actor()` 优先加载 `act.pth`，避免 `find_pth_files()` 误选旧 checkpoint。
- 新增 `get_quant_feature_state` / `set_quant_feature_state`：08/09 的 val/test 复用 train 的 scaler / PCA / 异常值阈值 / 保留列。

### Packaging

- `pyproject.toml`、`minibt/__init__.py`、`README.md` 版本统一为 **1.3.3**。
- 新增包内发布资料：`CHANGELOG.md`、`RELEASE_NOTES.md`、`RELEASING.md`。
- `MANIFEST.in` 将上述资料纳入 sdist；wheel 仍只包含运行时包、数据与扩展模块。

> 1.3.3 的逐项修复（P44–P185、10-19 / 10-21 / 10-22 / 10-23 / 10-25 补充）
> 记录在 `minibt_docs/docs/changelog.md` 的 `[v1.3.3]` 一节。

## [1.3.2] - 2026-10-16

- `signal_backtest(gui=...)`、多策略权益 / 回撤对齐、`from_signals` 报表口径
  修复、`KLine.run` 的 `.ta` 竞态修复。

更早版本见 `minibt_docs/docs/changelog.md`。

<!-- build: mwbzjn05 -->
