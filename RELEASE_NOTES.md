# minibt 1.3.5 发布说明

**发布版本**：`1.3.5`
**发布日期**：2026-11-03
**Python**：>= 3.12
**许可证**：MIT
**依赖**：`pylightcharts>=0.1.8`（本版升了一版前端资源）

## 一句话

1.3.5 是 1.3.4 之后的 **desk 收尾版**：回测结果页的「回撤」副图可关（默认关）、
参数优化页大修（优化设置 + 参数网格编辑器，图表不再空白、目标不再恒为 0）、
回测页浅色主题不再有黑块且回放视窗不再漂移；顺带修好「加载策略后再加指标会
互相清线」「删一个副图连带删另一个」「多合约盈亏副图空白」，
以及编辑器里 `minibt` 的悬停 / 补全（含手动指定路径）。

## 主要内容

### 1. 回测结果页：回撤副图可关

- 新增 `Config.drawdown_plot`（`minibt/utils.py`，默认 `False`）+
  `resolve_drawdown_plot(strategy, default=False)`；
- `False` → 结果页 = **K 线 + 权益 + 盈亏** 三格（省一格高度）；
  想要回撤副图：`self.config.drawdown_plot = True`；
- 覆盖 `Bt().run()` 回测窗口、回放窗口、desk 回测 / 参数优化；
  多策略开关不同时页面自动重建（不会串格）；旧数据没有该键时按「显示」兼容。

### 2. 参数优化页大修

- **「优化图表」不再空白**：新增 `_normalize_opt_rows()` 把 grid / optuna 两种引擎的
  结果统一成 `values_i` + `params_<名称>`（grid 引擎列名是「目标名 + 裸参数名」，
  前端以前一个点都找不到）；
- **「按当前目标重新优化」真的按选中目标跑**：`_indicator_config()` 从写死
  `target='sharpe'` 改成「用户设置 → 指标自带 `op_config` → 由 `params` 推导」，
  目标 / 权重 / method / n_jobs / n_trials / sampler / pruner / 参数网格全部生效；
- **「优化设置」+ 参数网格编辑器**：目标权重下拉（`±1 / ±2 / ±0.5`）、
  method（grid / optuna / ga）、n_jobs、n_trials、sampler、pruner；
  参数一行一个（参数名也是下拉）+ 类型（数值范围 / 固定选项 / 固定值），可增删。

### 3. 优化目标不再恒为 0

- 以前 `_calc_qs_metrics()` 只算 9 个指标，`OPTTargetType` 里其余 60 多个
  （含 `profit` / `result`）一律落成 `0.0` → 优化等于没优化；
- 现在补上 `result` / `profit` / `profit_rate` / `total_return`，其余目标现场用
  `quantstats.stats.<name>` 补算并缓存；算不出标量的目标（`monthly_returns` 这类）
  降级为 0 并**提示一次**（不再静默）；单腿与配对引擎都改。

### 4. 回测 / 参数优化页的图表与浅色主题

- **等待页不再黑底**：回测中 / 参数优化中 iframe 的占位页在构造时就装上并跟随主题，
  `/strategy_chart` 出错页、`pylightcharts` 导出 HTML 的 `<body>` 同样跟随；
- **副图分隔线更淡**：浅色 `rgba(100,116,139,.32)` → `rgba(224,227,235,.95)`
  （`themes.LIGHT['pane_separator']` 同步 `#B6C4D6` → `#E0E3EB`）；
- **回放视窗不再漂移**：`applyBars()` 只补「setData 前后视窗的实际位移差值」，
  可视 K 线根数恒定、最新 K 线到右边的距离不变（以前每拍多滚一根 → K 线越跑越偏、
  撞到边界后可视根数变小）；
- **图表工具栏**：「画线工具 / 删除画线工具」改成图标（铅笔 / 橡皮擦，名称在 tooltip）。

### 5. 多合约回测的盈亏副图空白

- 同一根 K 线多条腿成交 → `pnl` 出现重复时间戳 → lightweight-charts **渲染期**
  抛 `Value is null` → 整个 pane 画不出来（副图在、坐标轴在、就是没有线）；
- 新增 `pages._collapse_time()`：盈亏按同一根 K 线求和、权益 / 回撤取最后，
  交易连线 / 方向标记同样按时间去重。

### 6. 多布局 / 实时图表

- **加载策略后再加指标不再互相清线**：格 2..N 的指标补丁统一带
  `items = 策略线 + 指标线`（`_cell_indicator_payload()`），完整库指标的
  后台合并补丁也补策略线并回写缓存；
- **删一个副图不再连带删另一个**：`IndicatorLayer` 按 pane 对象身份算实际下标，
  且「LWC 已自动收掉空 pane」时不再调 `removePane()`；
- **画线工具条**：到上方工具栏 / 左右间距 0、工具条直角，图标悬停显示名称 + 快捷键；
  多布局共用一套工具、绑定最后点击的那一格，按「合约|周期」本地持久化
  （`~/.minibt/desk/drawings.json`）。

### 7. 编辑器：`minibt` 的悬停 / 补全

- 根因：jedi 的默认环境 `sys.path` 是子进程快照，「源码运行、minibt 未安装」时
  看不到仓库根 → `minibt.xxx` 的悬停 / 补全 / 跳转全空；
- `lsp.py::editor_sys_path()` 显式拼 sys.path（**源码仓库根 → 进程 sys.path →
  文件 / 工作区 → PYTHONPATH → site-packages**），`find_repo_roots()` 从正在编辑的
  文件向上找仓库根（仓库搬家 / 改名也能跟）；状态栏 LSP 徽标 tooltip 显示解析路径；
- 设置 → 个性化 → 编辑器新增「**手动指定 minibt 路径**」（默认关，改完即时生效）。

### 8. 加指标的成败提示

- 「编辑器 → 加到图表」以前无论成败都写「已加成功」；现在 `_on_*_add_indicator`
  返回 bool，只有真加上图才提示成功，失败只报错；
- 个人指标报错附**写法提示**：`self.ha` 是方法要写 `self.ha()`；
  `__init__` 里 `return` 元组不算出线（用 `self.lines.<名字>` 或改成 `next()` 返回元组）。

### 9. 新增「指标和策略」页（仿 TradingView）

入口：首页左侧「工作区」、顶栏「＋ → 指标和策略（TradingView 指标库）」、
命令面板（`Ctrl/⌘+P`）。详见手册
[13.28 指标和策略](../minibt_docs/docs/minibt_desk/manual/13.28_indicator_strategy_library.md)。

- **卡片库**：minibt 自带的 **114 个 TradingView 指标**，按分组 / 关键词 / 收藏查看，
  一页 **24 张**；卡片缩略图自动生成（指标按真实线样式画、策略跑一遍取线），
  **深浅两套**封面（`_light` / `_dark`，互不覆盖）；
- **点卡片 = 完整的本地图表**：工具栏 / 指标 / 模板 / 预警 / 回放 / 布局 / 交易 /
  二级报价 / 截图全在（画线导航栏默认收起），打开即展开底部「交易 / 编辑器」，
  自动载入数据、加指标并打开源码；**同一个指标只开一次**（再点跳过去）；
- **代码落到个人目录**：`~/.minibt/personal/indicators|strategies/<名字>.py`，
  头部 `# coding: utf-8` + `from minibt import *`，只取对应类 + **依赖类闭包**
  （`CCIStrategy` 会带上 `CCI`），样板 import 去掉；已存在不覆盖、老模板自动重建；
- **收藏**：卡片 `☆` / 图表页工具栏 `★` / 顶栏页签 `★` 三处同步；「收藏」跨分组，
  且只显示仍在默认 / 用户分组里的条目；
- **用户分组**：下拉框「＋ 添加指标和策略」选文件夹（递归 `.py`，分组名 = 文件夹名，
  存 `~/.minibt/desk/tv_groups.json`），「－ 删除」只删记录不动文件；
- **卡片右键**：打开指标 / 策略、在图表上使用（选已打开的本地 / 实时图表）、
  重载图表（单张重算，深浅两套）；工具栏「截图」会把 PNG 写到
  `~/.minibt/exports/` **并覆盖当前主题的卡片封面**（卡片右上角「指标 / 策略」
  标记改成 HTML 层，截图后不会丢）；
- 「刷新」右边新增「重载图表」（整页 24 张，后台线程逐张推送）；页签条支持滚轮横滚；
  卡片超过一屏后右下角出现「回到顶部」圆钮。

### 10. 指标表格 / VP（成交量分布）跟随鼠标

- **档区窗口修正**：VP 的 `vpLo/vpHi` 现在与指标同一套**滚动 500 根**窗口
  （以前用了 `price_bars or 120` → 分布被压扁、挤在价格区间下半部分）；
  实时图表同样修好（`realtime._vp_spec()` 默认 500）；
- **表格定位**：指标表格挂在**图表区**（`.desk-cell-main` / `.desk-chart-host`）
  而不是页面级容器 → 二级报价出现时不再遮挡、也拖不出图表；
- **十字线按格订阅**：换布局 / 切合约会重建 chart 实例，以前记"已订阅"的布尔值
  导致新图表再无十字线事件 → 表格 / VP 只有实时更新；现在记的是 chart 实例本身；
- **跟随的三条规则**：鼠标在历史 K 线上（且在动）→ 显示历史值；**停住 2 秒** →
  自动回实时；在**最新那根** / 右侧空白 → 立刻用最新数据。

## 升级注意

- **依赖升级**：`pylightcharts>=0.1.8`（desk 前端资源随该版本重建）。
- 回测结果页**默认不再显示回撤副图**：需要就 `self.config.drawdown_plot = True`。
- 升级后**重启 desk 进程并刷新页面**（Python 与前端 bundle 都更新了；
  回测图的 HTML 由 Python 生成，建议重跑一次回测）。
- 参数优化页的「方法 / 试验次数 / 采样器 / 参数网格」留空 = 跟随策略自带的
  `op_config`（老用法不受影响）。

## 安装

```bash
pip install -U minibt==1.3.5
# 或
pip install -U "minibt[dev]==1.3.5"
```

## 验证

```bash
python -c "import minibt; print(minibt.__version__)"     # 1.3.5
python -c "from minibt import Bt, Strategy; print(Strategy.config.drawdown_plot)"
minibt --help
# 依赖：pylightcharts 需要 >= 0.1.8（dist/ 里同名 wheel）
python -c "import pylightcharts; print(pylightcharts.__version__)"   # 0.1.8
```
