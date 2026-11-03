# minibt 更新日志

本文件记录 **minibt Python 包** 的发布信息；完整的产品更新（含 desk / miniqt /
VS Code 扩展）请同时参考：

- 官网更新日志：<https://www.minibt.cn/changelog/>
- 仓库完整记录：`minibt_docs/docs/changelog.md`

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

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
