# Changelog

All notable changes to `pylightcharts` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/) and this
project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.6] - 2026-10-27

`QtPanel` 支持自定义宿主页，给 **minibt desk**（报价 + 看盘，纯 JS/TS UI）用。

### Added

- `QtPanel(parent, url=...)`：不传仍是原来的图表宿主页 `index.html`，传路径
  就能加载任意网页（桥接 / qwebchannel / 脚本队列完全一致）；
- `pylightcharts/js/` 新增 `desk.html` / `desk.js` / `desk.css`（由 `jslib`
  的 `npm run build` 生成，供 minibt desk 使用）；
- **新增 `IndicatorPicker` 指标选择器插件**（`pylightcharts.panels.IndicatorPicker`）：
  左树分组 + 搜索 + ★ 收藏 + 来源列；`on_pick` / `on_favorite` 事件；
- **新增 `TemplatePicker` 指标模板插件**（`pylightcharts.panels.TemplatePicker`）：
  模板列表（N 个指标）+ 应用 / 删除 / 保存当前；`on_apply` / `on_delete` /
  `on_save` 事件；示例 `examples/13_panels/14_indicator_picker.py`；
- **新增 `SymbolSearch` 商品搜索插件**（`pylightcharts.panels.SymbolSearch`）：
  本地 / 远程两种模式、键盘 ↑↓/Enter/Esc、`on_query` / `on_pick` 事件；
  新增 `addLabel` 按钮 + `onAddCallback`（本地图表「添加数据文件夹」用）；
  示例 `examples/13_panels/13_symbol_search.py`；
- **新增 `AlertDialog` 预警对话框插件**（`pylightcharts.panels.AlertDialog`）：
  价格 / 穿过·上穿·下穿 / 到期 / 消息 / 动作 / 手数 + 已有预警列表，
  `on_create` / `on_delete` 事件；示例 `examples/13_panels/15_alert_dialog.py`；
- **新增 `QuoteBoard` 行情报价插件**（`pylightcharts.panels.QuoteBoard`）：
  类型/交易所 chips + 报价表 + 可选滚动条 + **加载中/暂无数据** 两种空表文案，
  事件 `on_click / on_double_click / on_context / on_filter / on_refresh`；
  示例 `examples/13_panels/12_quote_board.py`（含 `--check` 与 `--snapshot`）。

### Fixed

- **`custom-series` 的类型声明重复**（`Shape` 里 `borderColor` /
  `borderWidth` 各声明了两次）→ `tsc --noEmit` 报 `TS2300: Duplicate
  identifier` 4 条，虽然不影响构建（esbuild 不做类型检查）但把真正的类型错误
  淹掉了。现在合并成一处（同一对字段既用于图形描边、也用于标签框）✓
- **`legend.ts` 导出图标常量**（`GEAR` / `EYE_OPEN` / `EYE_CLOSED`）：
  minibt desk 的指标图例复用它们，保证「设置齿轮 / 眼睛」和 miniqt
  看盘窗口**长得一模一样**（以前 desk 用的是 emoji `⚙` / `👁` ✗）。
- **图例设置齿轮颜色 / 描边**：`.legend-settings-switch` 改为 `color: inherit`，
  与眼睛 / 图例文字同色；`GEAR` 线宽改成 2，深色近白、浅色近黑 ✓。
- **Sparkline 按真实宽度 / DPR 绘制**：隐藏时不再按 80px 画完再被 CSS 放大；
  支持父容器宽度兜底，线宽略增，迷你图价格线更清晰 ✓。

### minibt desk (bundled UI)

#### Added

- **行情报价有行但价格不更新 / 只有缓存**：`FuturesFeed.valid_symbol()`
  以前拿 `_data['symbols']` 当白名单，局部查询结果会把缓存里的合法合约
  全部挡掉，`quotes()` 返回空；现在只拉黑行情泵明确报“不存在”的合约，
  实测 DCE a/m/pp 的 last / bid 正常刷新。
  期货 `visible` 为空时取 `_last_rows` 前 200 个兜底刷新；股票仍按富途订阅池 / 100 额度逻辑不变。
- **所有交易所合约查询返回空的根因（本轮）**：`BaseFeed._fast_query()`
  包装 `_get_symbol_list` 时参数名写成 `filter_`，而 TqSdk 用关键字
  `filter=...` 调用 → 每次 `query_quotes` / `query_cont_quotes` 都抛
  `TypeError` 被吞掉，DCE / CZCE / INE / GFEX / INDEX 全都查不到；
  现在同时兼容 `filter_` / `filter=`，实测 DCE CONT_MAIN 23、FUT 250、
  CZCE 243。
- **实时 VP 鼠标空白区 / 离开图表**：`VpOverlay.onCrosshair()` 遇到
  “最后一根~右边缘”的未来时间以前直接 return，`mouseIndex` 停在上一次位置
  → VP 消失；现在统一回落到 `mouseIndex=null` 并重画最新一根。
- **VP 图例眼睛**：pylightcharts 原生图例的眼睛只切 series，VP 是 canvas
  覆盖层；现在原生眼睛也回调页面 `toggleIndicator()`，和自定义眼睛 /
  设置里的「显示该指标」共用 `cellHidden` 状态。
- **行情报价过期缓存兜底**：`SymbolCache.get_any()` 允许读取已过期合约
  清单；DCE / CZCE 这类超过 24h 的旧缓存也会先显示，再后台刷新，
  不因网络 / 查询失败把页面清空。
- **行情报价改为 miniqt 同款缓存优先**：
  - 切换类型 / 交易所时先秒开本地 `desk_symbols.sqlite3` 缓存（当天有效）；
  - 缓存新鲜时不再每次切筛选都发网络查询；过期 / 手动刷新才更新；
  - 过期缓存先显示，后台刷新失败也不会把列表清空；
  - 合约清单仍按天更新，联网成功后写回缓存。
- **DCE / CZCE / INE / GFEX / INDEX 合约一直“初始化中”**：
  `_retry_empty_rows()` 以前每 2 秒就重置异步 `SymbolList`，而 TqSdk
  某些交易所的 `query_quotes` 需要 3–8 秒才回 → 查询永远被丢掉；
  现在同一查询至少保留 10 秒再重置，2 秒重试只读同一个 `SymbolList`。
- **首屏只有 2 根 K 线 / 可视范围只有几根**：
  - `_refresh_tabs()` 记录 `_kline_frame_len`；TqSdk 从占位的 2 根补齐到
    完整历史时自动 **full replace**，不再永远只推最后 2 根；
  - 前端 `setBars(replace=true)` 发现根数明显增长时重新 `fitContent()`，
    避免可视范围停在最初 2 根。
- **`bandstyle` 色带恢复**：`IndicatorLayer.apply()` 以前在创建 pacU/pacL
  线序列**之前**调用 `_applyBands()`，此时 `_seriesOf(lowerKey)` 还是
  null → `ScalpingPullBackTool` 之类的主图色带永远不显示；现在线序列建完
  后再挂 `LineFill`，副图/主图 / 本地 / 实时共用修复。
- **个人 / TradingView `BtIndicator` 的 `isplot=False` 信号列恢复样式**：
  `_to_items()` 以前先按 `isplot=False` 跳过列，导致
  `ScalpingPullBackTool` 的 `long_signal` / `short_signal` 根本不生成
  `SignalStyle` 箭头；现在信号列即使 `isplot=False` 也会走
  `signalstyle` 生成 marker，普通数据列仍然不画。
- **内置指标目录过滤多合约 / 非 K 线方法**：
  - `Pair`、`Factors` 是多合约专用，指标菜单 / 衡量标准 / 策略内置指标
    都不再加载；
  - 目录构建最后统一过滤各库 `NON_KLINE_INDICATORS`（数学 / 逻辑 / 时间
    工具，如 `pta_ZeroDivision` / `ti_abs` / `talib_ADD` / `tqfunc_crossup`）；
  - `TuLip` 类补充 `NON_KLINE_INDICATORS`（abs / add / crossany /
    crossover / lag / max / min / sum …）；
  - `CATALOG_SCHEMA` 升至 7，旧目录缓存自动失效；
  - 审计：TqTa / FinTa 的方法都是 K 线指标；TradingView 不动；
    Pair / Factors 整体排除。
- **保存的布局键不能再回退成单图**：`applyLayout()` 只把 `payload.key`
  当预设（`single/h2/h3/grid4`）时用 `layoutSpecByKey()`；用户保存的布局
  key（如「布局1」）改用 `count / cols / rows`，本地图表配对策略布局
  正常显示两张图，实时图表同类路径同步修复。
- **图表字体大小默认值改为 13px**（设置页 / 实时图表 / 本地图表 / 回测图统一）。
- **minibt desk 日志降噪**：注释 `_reload_klines()` 里的
  `图表数据长度 → N 根` 日志（恢复默认 / 改长度会触发两次，重复刷屏）。
- **minibt desk 指标刷新频率设置（设置 → 图表设置）**：
  - 主图指标刷新间隔：10–3000ms（默认 1000ms）；
  - 副图指标刷新间隔：10–3000ms（默认 1000ms）；
  - VP / 表格刷新间隔：10–3000ms（默认 1000ms）；
  - VP / 表格「只在新 K 线更新」开关（默认关；开启后开销最低）；
  - K 线推送不受指标设置影响，保持即时推送（当前最后一根变化即推）；
  - 「恢复默认设置」改为**只恢复当前图表配置页**（历史长度 / 数据长度 /
    字体 / 十字线 / 持仓线 / 挂单线 / 指标刷新），不再只重置 K 线长度，
    也不影响图表颜色 / 模拟账户 / 主题；
  - 修复前端 `chart_reset` 自己手写 defaults、没有发送给后端的问题：
    现在统一由后端 `reset_chart_settings()` 清理并回推，指标刷新 4 项
    也会恢复默认（主图 / 副图 / VP 表格 1000ms，新 K 线开关关闭）。
- **minibt desk 实时图表表格 / VP（本轮补充）**：
  - 实时图表 `tablestyle` 在鼠标不在历史 K 线上时，每 1 秒按最后一根
    重算一次表格（以前只在鼠标 / 回放时更新）；
  - 完整库指标（VP / 表格）后台计算期间 `pending=true`，前端保留上一份
    VP / 表格，不再每次新 K 线把它们短暂清空；
  - 前端 `VpOverlay` 与本地图表共用，实时 / 多格都走 `_syncVpOverlay`。
- **minibt desk 指标增量更新 / 性能分析**：
  - 同一根 K 线内只重算尾部 `INDICATOR_TAIL_BARS`（默认 1200 根），
    不再每 0.5 秒重算全部历史；
  - 后端只推 `{mode:'last'}` 的最后一点，前端 `IndicatorLayer.applyLast()`
    用 `series.update()` 增量更新（蜡烛 / 线 / 柱都支持）；
  - `_refresh_tabs()` 复用已拉取的 `frame`，不再让 `indicator_payload()`
    二次请求完整 K 线；K 线推送只转换最后 2 根；
  - `personal._import_file()` 缓存用户指标模块；`indicator_catalog._kline_of()`
    缓存 key 加入首尾时间 / 长度 / 最后 close，避免同根 K 线复用旧 KLine；
  - 新增 `MINIBT_DESK_PROFILE=1` 才输出的「看盘 tab 明细」分层耗时日志
    （klines / bars / book / position / orders / cell_bars / strategy / indicator）。
- **minibt desk 审计报告**：新增 `minibt_docs/docs/minibt_desk/audit_2026-10-25.md`，记录 P0/P1 问题、测试缺口、实盘验收清单与功能扩展路线。
- **本地图表教程（13.17–13.21）**：新增「指标规则 / 加到图表」「回放与本地模拟账户」「策略回测」「参数优化」「指标样式示例」五篇；配套 `tutorials/desk/local_chart/`（单合约 / 配对策略、`signal_backtest` / `pair_backtest`、`OpConfig` / `OptimizeConfig`）和 `tutorials/desk/indicators/style_zoo/`（8 个样式指标分类示例）。
- **编辑器帮助补充智能添加规则**：`get_kline` 自动选布局 / 校验本地或天勤数据、`klines1/2` 数量限制、配对 `pair_klines`、回放自动交易与 `config` 账户、三种回测 / 优化入口。
- **指标 `pair_backtest` 回测/优化支持（P167）**：指标类声明
  `pair_klines = (腿A, 腿B)` 时，desk 的「开始回测 / 参数优化」都走
  `IndFrame.pair_backtest(...)`；回测和优化后保留两条真实合约的 K 线、指标、
  交易记录与图表（修复 test_5 合成价差只有一条曲线、没有合约图的问题）。
  `pair_backtest_kwargs` 支持 `size / commission / com_type / leg_size_ratio /
  margin_rate / init_cash`。新增 `test_6.py`（配对信号参数优化）和
  `test_7.py`（配对交易回测）示例。
- **策略参数优化结果页修复**：单目标 Optuna CSV 的 `value` 自动规范成
  `values_0`（以前前端只认 `values_*` → 优化图表为空、参数排名 0 个）；
  「参数排名」按 `params_*` 参数名展示；单目标「帕累托」改为
  trial number → value 的优化历史图。
- **minibt desk 本地模拟账户跟随策略账户参数**：
  - 回放开始使用 `strategy.config.value` 重置账户（默认当前代码为 1,000,000）；
  - 每合约同步 `price_tick / volume_multiple / margin_rate / commission /
    slip_point`；
  - 手续费支持 fixed / percent / tick，且**每合约可不同**（本地 CSV 的
    `KLine.fixed_commission = ...` / `config` 都会生效）；
  - 账户改为期货保证金口径：权益 / 占用保证金 / 可用资金 / 资金使用率；
  - 策略自动成交按 minibt `slip_point` 加滑点；
  - 无策略 / 手动交易仍使用 desk「模拟账户」的初始资金与全局手续费。
- **minibt desk 策略自动布局 / 自动选合约**（本地图表 + 实时图表）：
  - `get_kline(LocalDatas.xxx)` / `get_kline("SHFE.xxx")` 会在「加到图表」时
    自动识别合约、选布局（2 个 → 左右两图）、按顺序加载各格，再加载策略；
  - 本地图表按本地 CSV 校验；实时图表先到天勤报价校验（不存在 / 已下市
    弹窗提醒，不改变当前布局）；
  - `klines1/2/...` 写法无法从策略里推断合约 → 必须用户先调好布局并加载
    合约；数量不够时弹窗提醒，不再擅自用其它 tab 凑数；
  - 单合约 / 多合约策略都支持；实时图表下单走当前天勤模拟 / 实盘账户
    （`TargetPosTask`）；多布局第 2..N 格 K 线 / 指标 / 策略线按格推送；
  - 切换天勤模拟 / 实盘账户时清理旧 `TqObjs`，避免仍下到旧账户。

#### Changed

- **策略实盘启动协议**：`strategy_live_start` 现在必须带 `confirm: true`；
  前端会弹 `window.confirm`，外部脚本 / 自定义前端需要同步补字段。
- **浏览器壳命令鉴权**：`POST /callback` 需 `X-Desk-Token`，`GET /events`
  需 `?token=`；外部集成不再能匿名调用 desk 命令。
- **股票真实下单失败**：`StockApi.insert_order()` 富途拒单时抛
  `RuntimeError`（不再静默本地成交）；调用方需处理异常。

#### Fixed

- **天勤登录后期货行情一直空 / 首页主力无数据**：
  - 天勤刚登录时 `TqApi` 的 symbols / 异步 `query_cont_quotes` 还没返回，
    第一次 `CONT_MAIN · DCE` 取到空表后以前会写入 `_skip_markets`
    **永久跳过**，只能手动点「刷新」；现在空表改为 **2 秒后自动重试**，
    并在新连接时清空上一轮跳过记录；
  - 首页「市场全景 / 主力」固定使用天勤 `self.futures`，不再跟随报价页
    当前筛选（报价页停在股票时 `current_feed()` 是富途，会误查股票源）；
  - 首页自选 / 主力仍然每 2 秒重新取报价，天勤初始化完成后自动出数。
- **不存在的天勤合约不再拖垮行情泵**：
  - 实时策略校验不再直接 `api.get_quote("SHFE.ag2701")`，改为先查
    天勤合约清单；不存在的合约（如 `test_4.py` 里的 `ag2701`）直接提示
    「合约列表里没有 / 可能已下市」，不会触发 GraphQL 错误；
  - `FuturesFeed` 记录已确认的合约；行情泵报“不存在”时自动取消订阅并
    清理 sqlite 合约缓存，避免下次启动再次订阅；
- **修复 `_fast_call` 把天勤报价 / 合约查询一并置空的问题**（本轮根因）：
  - `get_quote_list()` 在 `loop.is_running() == False` 时会
    `while not task.done(): wait_update()`；只把 `wait_update` 换成
    `False` → 立即 `TqTimeoutError`，首页 / 报价永远没有价格；
  - 现在 `_fast_call()` 临时让 `loop.is_running()` 返回 True，直接拿
    `QuoteList` / DataFrame，订阅任务交给下一拍 `pump()` 填充；
  - `FuturesFeed.contracts()` 改用 `start_symbols()` 缓存同一个异步
    `SymbolList`，2 秒重试读取已填充结果，DCE / CZCE 不再永久 0 行；
  - 行情泵遇到 `rb2701` / `ag2701` 这类不存在合约时，解析错误里的代码，
    取消订阅并清理本地合约缓存；默认实时图表不再用 `KQ.m@SHFE.rb` 兜底；
  - 首页市场全景优先从天勤合约清单取真实 CFFEX 主力，减少主连映射风险。
- **minibt desk 实盘安全 / 回放修复（审计 2026-10-25）**：
  - 本地回放 `buy()/sell()` 兼容完整 `stop / reverse / exectype / valid`
    参数，CCI 停止线恢复完整时间轴；
  - `allow_trading=False` 同时拦截策略实盘；策略实盘启动需二次确认；
    `Desk.close()` / 浏览器壳退出停止实盘子进程；子进程退出释放实例锁；
  - 浏览器壳 `/callback` 加 `X-Desk-Token`，`/events` 加 query token，
    CORS 只允许 desk 自身 origin；
  - 股票真实下单失败 / 撤单失败不再记为本地成交 / 已撤；
  - 切换模拟 / 实盘账户清空 `TargetPosTask` 缓存；
  - 全平 / 反手不再吞掉失败；平仓识别 `volume_long / volume_short`；
  - 股票 K 线不再错误 +8 小时；
  - 前端右键「加到图表」使用右键文件、Home 空 bars 不循环请求、
    导出历史等待后端补丁、回测/优化日志不再丢弃。
- **本地期货模拟账户 SQLite 持久化**：`LocalSim` 支持 `db_path`，落盘
  账户 / 持仓 / 委托 / 成交 / 权益曲线 / 品种统计 / 合约参数 / 最新价；
  `Desk.local_sim()` 默认 `~/.minibt/desk_sim.sqlite3`，`Desk.close()` 保存；
  pytest 默认不落真实目录（`MINIBT_DESK_SIM_DB` 可覆盖）。
- **参数优化取消**：Strategy / 指标 Optuna 回调检测取消标志后
  `study.stop()`，不再等全部 trials 跑完。
- **文档修正**：`candlestyle` / `vpstyle` / watermark 已支持；本地期货
  模拟账户已落 SQLite（不再是“内存待补”）。
- **Qt 测试进程崩溃修复**：`QT_QPA_PLATFORM=offscreen`（或
  `PYLIGHTCHARTS_NO_WEBENGINE_CACHE=1`）时跳过
  `QWebEngineProfile.defaultProfile()` 缓存操作，不再 exit 127；
  全量 desk / vscode 测试 **821 passed**。
- **测试旧断言清理**：`st:` → `editor:`、前端源码 grep、旧接口、
  leading-NaN、时间 flaky 等约 31 个测试同步到当前实现。
- **编辑器保存路径限制**：`personal.write_file(path, root=...)` 只允许
  个人目录 / 当前资源管理器根目录；HTTP/编辑器命令不能借保存写任意路径。
- **信号方向修复**：`long_signal` 的 `-1` 现在画成空头箭头（以前按列名
  一律画成买），信号列测试恢复。
- **合约索引初始化修复**：首次 `refresh_symbol_index()` 不再因缺少
  `_symbol_rows` 抛 `AttributeError`。
- **前端剩余项**：
  - 收藏策略补 `label/path`，指标菜单 / 右键菜单可直接按文件路径
    `editor_add_indicator` 加到图表；
  - 参数优化表增加筛选框 + 表头排序；
  - 最优参数写回支持嵌套 `params=dict(...)` / tuple / 字符串；
  - Web tab 只接受网页 tab iframe 的 `event.source`，URL 做 HTML 转义；
  - 本地图表工具栏补回「二级报价」按钮。
- **本地图表模板 / 完整布局管理**：
  - 指标模板 `save_template` / `apply_template` 支持 `local: true`，按当前
    CSV / 格保存与恢复；
  - 布局 `layout_save` / `layout_apply` / `layout_update` 支持 `local: true`，
    保存每格 CSV + 指标并逐格恢复；
  - 修复 `TemplatePicker.onApplyCallback` 只刷新列表、不真正应用模板的旧 Bug；
  - 本地图表工具栏补回「模板 / 二级报价」，布局按钮改为完整布局菜单。
- **普通回测取消**：`Strategy._execute_core_trading_loop()` 每根 bar 检查
  `_cancel_check`；`StrategyLab._run_with_cancel()` 安装 / 恢复钩子，
  取消不再等整段 `bt.run()` 跑完。
- **低优先级 UX 收口**：
  - 账户空表显示「（暂无数据）」；
  - 登录框未记住密码时清空旧密码；
  - 菜单 / 指标菜单 / 参数浮层关闭时移除 document 监听；
  - 1–4 根短数据回放初始索引不再越界；
  - 截图不可用时给 toast；
  - 顶栏补「全局搜索 / 运行日志」；
  - 设置 → 个性化补指标选择器默认分组 / 播放条只显示有报价 /
    首页自选默认分组，并接入 `watch_default_group`。
- **Home 工作区 / Option / 股票交易**：
  - Home 三个占位入口改为真正页面：图表工作台、回放实验室、预警中心；
  - 报价页新增「期权列」入口（`行权价 / 到期日`），并修复换列后收藏点击失效；
  - 股票登录框新增「启用交易 / 交易环境（模拟 / 真实）」；
  - 真实股票订单改为 `SUBMITTED` 提交态，新增 `order_list_query` /
    `deal_list_query` 轮询委托与成交，不再本地直接成交。
- **本地图表点击日志降噪**：鼠标每点一次图表就打印
  `当前交易合约：…` 会刷屏，已注释该日志（功能不变）。
- **TqSdk 断线不卡界面**：`BaseFeed._fast_call()` 在调用
  `get_quote_list` / `get_kline_serial` 时临时禁用内部 `wait_update`，
  断线时不再阻塞主线程 25–30 秒；恢复后自动继续刷新。
- **富途四市场模拟账户**：股票登录框新增交易市场（沪深 / 香港 / 美国 /
  日本，默认沪深）；`trd_market` 持久化并传给 `StockApi`，市场不匹配时
  自动重连 / 明确提示。
- **股票下单数量单位**：修复 `_on_place_order` 只读 `volume` 忽略前端
  `qty` 的问题（之前永远下 1 股 = 碎股）；股票面板改为「股数」默认 100，
  期货仍为「手数」。
- **报价页重开 chips 丢失**：右上角全局搜索重新打开报价页时，
  `openQuote()` 重发 `quote_chips`，类型 / 交易所按钮不再全部消失。
- **首页账户切换 / 自选混合数据源**：
  - 账户概览「快期模拟 / 富途模拟」菜单，未登录项置灰，切换后账户卡和
    左下角摘要同步；
  - 首页自选每 2 秒刷新报价；股票走富途、非股票走天勤；市场全景由天勤负责。
- **全量测试恢复绿灯**：`tests/test_minibt_desk*.py` +
  `tests/test_vscode_desk*.py` → **821 passed**。

### Compatibility

- 老版本（0.1.5）没有 `url=` 参数，minibt 侧已做**自动降级**
  （建完 `QtPanel` 再手动 `load`），所以 minibt 仍可要求 `pylightcharts>=0.1.5`。

## [0.1.5] - 2026-10-16

Same engine, a small bug-fix release for the **browser / Jupyter** rendering
path plus defensive guards around the legend scripts (the native window path was
never affected).

### Fixed

- **The browser / Jupyter page could silently stop after the first topbar
  statement, leaving a blank chart** (the K-line loaded, every indicator was
  missing, and switching the theme made them reappear - the theme rebuild streams
  its statements one by one, so it dodged the bug). `StaticLWC` (`BrowserChart`,
  `JupyterChart`, `StreamlitChart`) joined every queued statement into one
  `<script>` with a bare `\n`, so a statement ending in `)` with no semicolon
  (the topbar's `xxx.intervalElements[0].click()`) glued itself to the next
  IIFE and the browser parsed `click()(function(){...})()` - a `TypeError` that
  aborts the **whole** block, so the K-line and every indicator `setData` after
  it never ran. Statements are now separated by `;` (same guard as
  `util.Batch` / `HeadlessChart`), and `window.callbackFunction` is defined
  **before** the first chart statement (it used to be appended at the end, so
  the initial switcher click threw `window.callbackFunction is not a function`).
- **Legend/menu scripts no longer throw when their series handle is already
  gone.** `enable_legend_settings` / `enable_legend_menu` / `pin_legend_row` /
  `remove_legend_row` read `window.<series>.series` first; a series deleted (or
  a stale tab) made that throw `Cannot read properties of undefined (reading
  'series')` and abort the rest of the batch. They now resolve the handle first
  and return when it is missing, and `_emit_snapshot` guards every streamed
  `setData` the same way.

## [0.1.4] - 2026-10-15

Same engine (Lightweight Charts v5.2.1), focused on the **runtime and UX
papercuts** found while driving real chart windows from `miniqt` / `minibt`: one
render-process hang, a family of "the chart silently stops drawing" bugs, and
the indicator-legend / marker / ticker surfaces those hosts kept working around
in Python.

### Added

- **`series.enable_legend_menu(config, func)`** — a settings (gear) button on a
  series' legend row that opens a **two-level JavaScript menu** inside the page
  (`参数` / `线型` / `线宽` / `线颜色` / `其它设置`). It is the Qt-free counterpart
  of `enable_legend_settings` (whose gear opens a PyQt card), so hosts without
  Qt (minibt / btplot) get the same settings surface; every change calls
  `func(series, kind, payload)` so the host can persist / recompute.
- **`chart.enable_legend_collapse()`** — the TradingView-style collapse button
  (`∧` / `∨ N`) below the indicator legend rows; it hides itself when there are
  no rows. It lives in the JS legend, so both the Qt and the browser hosts get it.
- **`chart.legend(..., text_visible=False)`** — hide the free `text` row (the
  title line above the OHLC readout), so the main row starts at the date.
- **`series.remove_markers(ids)`** — remove many markers with a single
  re-render, and `marker(..., size=)` now reaches the v5 marker primitive
  (`marker_list` / `update_marker` keep it).
- **In-pane horizontal-line labels**: `chart.horizontal_line(...,
  label_visible=True, label_background_color=, label_text_color=, label_font=)`
  draws `text` **inside** the pane (pinned to the left edge of the visible range)
  instead of only on the price axis. Setting `axis_label_visible=False` now
  really removes the axis badge (it used to keep widening the price scale by the
  label's length).
- **`series.skip_gap_segments()` / `prefer_single_gap()` / `repaint_gaps()`** —
  the NaN-break options the gap renderer needs: don't split hidden `fill_between`
  carriers, prefer the single-series transparent-gap path for realtime indicator
  lines, and re-send the data so a per-point colour follows a later
  `apply_options(color=...)`.
- **Panels**: `OrderTicket` (the buy / spread / sell ticket), plus
  `Column(trim=True)` (show up to `decimals` places but strip trailing zeros)
  and `DataGrid(font_size=)`.
- **`Ticker.set_data(items)`** — refresh a ticker **in place**, keeping the
  marquee animation running (it falls back to `set_items` when the symbol list /
  order changed).
- **Qt diagnostics**: the Qt host now forwards `console.error` / `window.onerror`
  to stderr through the existing bridge and logs render-process termination
  (`QWebEngineView.renderProcessTerminated` / `renderProcessResponsive`), so a
  "frozen" chart can be told apart from bad data.

### Changed

- **`legend=False` no longer fakes the series name.** The JS side builds a
  legend row for every series it is handed, so the old "empty name = no row"
  trick gave the series an empty name — which then broke column mapping. The
  real name is passed down and the row is removed explicitly
  (`series.remove_legend_row()`).
- **`create_line()` lines now break at `nan` like every other line**: `Line`
  carries `kind = 'Line'`, so the gap splitter recognises it.
- The legend OHLC readout is a **single line** (`date | O | H | L | C | V | %`)
  instead of two rows.

### Fixed

- **`watermark()` froze the render process** (`RunJavaScript` never returned
  again → the chart showed only its axes, no candles): the `setWatermark`
  script did not end with `null`, so PyQt6's `runJavaScript` tried to convert
  the **live `TextWatermark` pane primitive** (a native LWC object with circular
  references) into a `QVariant` and hung the renderer. The script now ends with
  `\nnull`, exactly like `Window.invoke`. This is what made miniqt's chart
  windows blank on every theme re-apply (they call `watermark('')` to clear an
  off watermark).
- **The same `null`-termination bug in `Window.invoke` and the generic
  `_invoke_assign`** (`add_series` / `add_custom_series` with a Qt host) and in
  every `TopBar` widget constructor: a live handle coming back as the script's
  completion value could freeze the renderer.
- **Script batches are joined with `;`** (`util.Batch` and
  `HeadlessChart.to_scripts`): ASI could glue a `null`-terminated script to the
  next IIFE and run `null(function(){...})`, which silently swallowed the rest
  of the batch (including `setData`).
- **`setMarkers` is wrapped in an IIFE** and the markers are sorted by time:
  the v5 marker primitive returned a live object and QtWebEngine's completion
  value collection hung on it; unsorted arrays could drop markers at random.
- **`inf` counts as missing data**: `util._has_missing` routes frames with
  `+/-inf` through the JSON path (where it becomes `null`) instead of the
  base64 block, which shipped a JS `Infinity` and broke autoscale / legend
  readouts.
- **`_single_datetime_format` no longer divides by zero** before any data (or a
  one-row frame) has set `_interval`.
- A **tile layout keeps its divider colour on a theme change**
  (`arrange_tiles` + `set_divider` re-issues the tile script), the **ticker**
  ignores `last=null` / `chg_pct=null` instead of printing `null`, and the
  horizontal-line axis badge no longer reserves space when hidden.

### Performance

- The single-series transparent-gap path is now the default for realtime
  indicator lines and for hidden `fill_between` carriers, so a fragmented line
  no longer creates (and re-creates) hundreds of internal series per second —
  the render thread no longer falls behind on `supertrend`-style half-`nan`
  lines, and a `set` no longer serialises the same payload twice.

## [0.1.3] - 2026-09-30

### Performance

- **NaN-gap lines draw with far fewer series**: a `Line` that breaks at `nan`
  used to create one internal `addSeries` + `setData` per contiguous segment -
  each is a webview round-trip and another browser repaint, so indicators looked
  like they were drawing "one line at a time, left to right" and loaded slowly.
  Now:
  * up to `Line.MAX_GAP_SEGMENTS` (64) segments keep the per-segment split
    (few series, clean tooltips);
  * above that the line becomes a **single series with transparent gaps**: gap
    points carry the previous value and a transparent `color`, and the engine -
    which colours each segment from its *starting* point - simply skips them.

  MACD-Bollinger `macd_up` / `macd_dn` (369 / 374 segments on the bundled test
  data) went from 743 internal series to 0 (`btplot` ~2.0 s -> ~1.1 s), and the
  all-`nan`-alternating band-boundary lines (`fill_up_low` / `fill_dn_low`,
  264 segments each) from ~1056 series to 4. `fill_between` bands keep breaking
  at those points too - the `LineFill` view treats a transparent point as a gap -
  so SuperTrend-style channels stay correct.

### Added

- **Multi-line labels in `shapes.text(...)`**: a newline inside `text` is now
  rendered as **several lines** (same convention as bokeh's `LabelSet`),
  spaced `line_height` (new keyword, default `1.2`) x `font_size` apart and
  anchored on `baseline` (`'top'` grows downwards, `'bottom'` upwards,
  `'middle'` keeps the whole block centred on `price`). Handy for per-point
  signal annotations such as ``'BUY\nCCI\nRSI'``.
  Covered by `examples/11_api_tour/21_text_multi_line.py`.
- **Full label styling on `shapes.text(...)`**: `offset_x` / `offset_y` (CSS-pixel
  offsets, scaled by the pixel ratio), `font_family` / `font_weight` / `font_style`
  (they build the canvas `font` string), and an optional label box -
  `background_color` (+ `background_alpha`), `border_color` (+ `border_alpha`,
  `border_width`) and `padding` (drawn behind the text, sized to the widest
  line, `
`-aware). All optional: omitted values keep the renderer defaults.
- **Inset floating tables**: `Table.set_position(...)` and
  `chart.create_table(...)` accept `margin_x` / `margin_y` (pixels from the
  nearest horizontal / vertical edge), so a table can be nudged clear of the
  top bar or the legend while staying pinned to its corner on resize. The
  `Table.set_colors(...)` helper keeps working unchanged.

### Fixed

- **A `nan` in either channel line now breaks the band too** (`fill_between` /
  `upper.fill_between(lower)`): the `line-fill` renderer used to build one closed
  path out of every point, so a gap in either line filled straight across it (a
  big ugly triangle at the break - same problem the line series had). It now
  fills one path per run of consecutive *valid* points, so the band stops at the
  gap and picks up again after it. The pane view had to learn about gaps as well:
  `ISeriesApi.data()` does **not** return whitespace items, so a series looks
  contiguous even where it has no values - the view now also compares the
  `timeToIndex()` of consecutive points and inserts a break when the logical
  index jumps. Covered by `jslib/test/line-fill.test.ts` +
  `jslib/test/line-fill-view.test.ts` (single run, gap in the middle,
  leading/trailing gaps, one-sided gap, fewer than two valid points) and by
  `examples/11_api_tour/23_fill_between_gaps.py`.

- **A `nan` in a `Line` series now breaks the line instead of connecting across
  it.** lightweight-charts v5 treats a whitespace item (`{time}` without a
  value) as "a time scale point only" and draws straight through it, so
  `[1, 2, 3, nan, nan, 6, 7, 8]` came out as one continuous line. The main
  series is now hidden (`lineVisible: false`) and every contiguous run is drawn
  by an extra, legend-less `Line` series that copies the main series' style -
  the price line, the last-value label and the legend row stay on the main
  series, and gapless data keeps the single-series behaviour (no extra work).
  Covered by `examples/11_api_tour/22_line_gaps.py` plus two bridge regression
  tests.
- **The native window no longer hangs when the entry script has no
  `if __name__ == '__main__':` guard.** On Windows / macOS the renderer runs in
  a `multiprocessing` child (`spawn`), which **re-executes the entry script**;
  without the guard the child dies before the window is ready, and
  `WebviewHandler.start()` waited on `loaded_event` **forever** (the script just
  looked frozen). It now polls the child's liveness with a timeout and raises
  the new **`pylightcharts.WindowStartError`** (exported from the package) whose
  message says exactly what to do: add the guard, or use a browser target
  (`BrowserChart` / `gui='pylightcharts_web'`).

## [0.1.2] - 2026-09-29

Correctness pass over the series lifecycle, the drawing primitives and the
local browser server — every change here came out of the bridge log
complaining at a real chart (page switches, window rebuilds, Ctrl+C,
sandboxed iframes).

### Added

- **`shapes.stem(price, baseline=0.0, color=None, width=1, style='dashed',
  cap=False, cap_radius=3)`** — a vertical stick from `baseline` to `price`
  (a "lollipop"), for per-bar values that read better as a deviation from a
  common base: per-trade PnL, distance from a moving average, volume at price.
  `style` defaults to `'dashed'`; `cap=True` puts a dot on the tip. Either way
  the item's `value` still drives the autoscale, so the pane range is not
  affected.
- **CORS on the local browser server** (`server.py`): responses carry
  `Access-Control-Allow-Origin` / `-Headers` / `-Methods` and `OPTIONS`
  preflights are answered with `204`, so the JS callbacks and the SSE stream
  keep working when the page is embedded in an opaque-origin / sandboxed
  iframe (Jupyter output frames, Streamlit, `srcdoc`).

### Changed

- Rebuilt `pylightcharts/js/bundle.js`: `removeSeries()` now also drops the
  legend row **by series name** (`e.series === series || e.name === name`),
  because the wrapper handle is not always resolvable at that point (a page
  switch or a window rebuild invalidates it).
- More regression tests: bokeh backtest/replay/realtime subprocess tests, the
  minibt → pylightcharts mapping layer (`tests/test_realtime.py`), theme and
  `Config` resolution, `shapes.stem`, a refreshed API-coverage baseline. Tests
  that need the (unpublished) `minibt` sources skip themselves.
- **The sdist is a full source tree again** (`MANIFEST.in`): it now carries
  `examples/`, `scripts/`, `docs/`, `tests/`, `jslib/` and `requirements.txt`,
  so `pytest tests -q` passes on an unpacked sdist instead of erroring on
  missing example files. `scripts/check_sdist.py` (run by CI) guards the
  manifest; `RELEASING.md` documents the whole release.

### Fixed

- **Deleting a series twice no longer logs "Value is undefined".** Every
  `delete()` path now goes through `Series._do_delete()`, which is idempotent
  (a `_deleted` flag): several managers keep a series in more than one list and
  used to emit `removeSeries({"$ref": ...})` for a handle the JS side had
  already dropped.
- **`Band` / `HorizontalSpan` / `VerticalSpan` are removed with
  `series.detachPrimitive(...)`.** They are v5 series *primitives*, so the old
  `detach()` call raised "`...detach` is not a function"; the detach is also
  skipped when the series they were attached to is already gone.
- **`overlay.add_symbol(...)` passes `price_line_visible` / `last_value_visible`
  / `title` as series creation options** instead of a follow-up
  `applyOptions` pass. That second call logged `Value is null` (LWC
  `ensureNotNull`) when the handle had already been dropped by a page switch or
  a window rebuild, which also aborted the rest of the queued script batch.
- **Ctrl+C on Windows prints `[pylightcharts] window closed`** instead of a
  traceback: `show()` catches the `CancelledError` / `KeyboardInterrupt` that
  `asyncio.run()` re-raises when the pywebview message loop is interrupted.
- The native window is created with `min_size=(width, height)`; a window
  narrower than the requested chart size made the startup `evaluate_js` return
  `null`, and the series' legend rows were lost with it.

## [0.1.1] - 2026-09-23

First release after the `0.1.0` preview: theming, custom-series shapes, panes,
infinite history and browser/live support are now feature-complete enough to
build on.

### Added

- **`shapes.marker(price, marker=..., offset=..., size=..., color=...)`** — a
  pixel-sized marker glyph for declarative custom series. `offset` (vertical
  pixel shift, positive = down) and `size` (pixel half-extent) are **pixels**, so
  glyphs keep their size at every zoom level. Supported `marker` names:
  `triangle` `inverted_triangle` `arrow_up` `arrow_down` `circle`
  `circle_cross` `circle_dot` `circle_x` `circle_y` `square` `dot` `dash`
  `cross` `asterisk` `triangle_dot`.
- **Themes** — `Window.theme(name)` (dark/light) plus `active_background` /
  `crosshair_label` accent colours, per-theme pane-separator colours and
  `layout.font_size`; the whole UI (chart, topbar, legend, tooltips, tables,
  report pages) follows one palette.
- **`chart.create_html_panel()`** (`HtmlPanel`) — a themed, full-bleed HTML
  overlay for report pages (statistics + trade tables).
- **Two price scales per pane** — `overlay.add_symbol(...)`,
  `scale_margins(...)` and independent left/right scales.
- **Infinite history** — `pylightcharts.history` + `events.range_change` driven
  loading, with gap-aware data encoding so the chart never connects across
  missing bars.
- **Browser targets** — `BrowserChart`, `chart.export_html()` and a stdlib
  SSE server for live charts (no Qt, no third-party server).
- **Qt-free chart widgets** and a `Window`-level `on_theme` callback.
- More custom-series helpers: `shapes.range_bar` / `box_plot` / `error_bar`
  presets, legend rows per custom series, and per-series `color_by`.
- Keyboard navigation, swing markers, `size=`, formatter `name=` and drawing
  primitives (trend line, box, horizontal line/span, `fill_between`).

### Changed

- `encode_series_data()` falls back to the JSON path whenever the data contains
  gaps, so `NaN` bars stay whitespace instead of silently connecting.
- `set()` on a single-value series matches a column **named like the series**
  (`{time, value}` style is reserved for OHLC/range series).
- Pane dividers are 1 px and only their **colour** and `enable_resize` are
  configurable.

### Fixed

- A script batch ending without `;` followed by one starting with `(` no longer
  breaks the whole batch (ASI hazard in `run_script`).
- `closeEvent` shadowed its own exception variable, raising `UnboundLocalError`.
- Blank chart on cross-origin `qwebchannel` initialisation (three injection
  modes + an ES2018 build target).
- Legend swatch/eye icons keep their colour (`currentColor`); tooltip bottom
  border is drawn; table borders/centring; page-topbar separator line.

### Notes

- `chart.screenshot()` captures canvases only — use `HeadlessChart.render()` for
  DOM overlays (legend, topbar, HTML panels).
- Real windows host the GUI in a child process, so parent processes should use
  `threading` rather than `QTimer`.

## [0.1.0] - 2026-08-13

- Initial preview release: bridged, near-full TradingView Lightweight Charts v5
  API coverage, declarative custom series, plugins, panes, layouts and
  tooltips.
